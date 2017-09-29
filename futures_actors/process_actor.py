""" Implements ProcessActor """
from concurrent.futures import _base
from concurrent.futures import process
from futures_actors import _base_actor
import sys
import os
import weakref
import threading
import multiprocessing

# Most of this code is duplicated from the concurrent.futures.thread and
# concurrent.futures.process modules, written by Brian Quinlan. The main
# difference is that we expose an `Actor` class which can be inherited from and
# provides the `executor` classmethod. This creates an asynchronously
# maintained instance of this class in a separate thread/process

__author__ = 'Jon Crall (erotemic@gmail.com)'


if sys.version_info.major >= 3:
    import queue
    from multiprocessing.connection import wait
    BrokenProcessPool = process.BrokenProcessPool
else:
    import Queue as queue

    class BrokenProcessPool(RuntimeError):
        """
        Raised when a process in a ProcessPoolExecutor terminated abruptly
        while a future was in the running state.
        """

if hasattr(process, '_ExceptionWithTraceback'):
    # Maybe we should just duplicate all futures structures to not be sensitive
    # to external code changes
    _ExceptionWithTraceback = process._ExceptionWithTraceback
else:
    import traceback
    # Python 3.4 does not define _ExceptionWithTraceback
    class _RemoteTraceback(Exception):
        def __init__(self, tb):
            self.tb = tb
        def __str__(self):
            return self.tb

    class _ExceptionWithTraceback:
        def __init__(self, exc, tb):
            tb = traceback.format_exception(type(exc), exc, tb)
            tb = ''.join(tb)
            self.exc = exc
            self.tb = '\n"""\n%s"""' % tb
        def __reduce__(self):
            return _rebuild_exc, (self.exc, self.tb)

    def _rebuild_exc(exc, tb):
        exc.__cause__ = _RemoteTraceback(tb)
        return exc


_ResultItem = process._ResultItem


def _process_actor_eventloop(_call_queue, _result_queue, _ActorClass, *args,
                             **kwargs):
    """
    actor event loop run in a separate process.

    Creates the instance of the actor (passing in the required *args, and
    **kwargs). Then the eventloop starts and feeds the actor messages from the
    _call_queue. Results are placed in the _result_queue, which are then placed
    in Future objects.
    """

    actor = _ActorClass(*args, **kwargs)
    while True:
        call_item = _call_queue.get(block=True)
        if call_item is None:
            # Wake up queue management thread
            _result_queue.put(os.getpid())
            return
        try:
            r = actor.handle(call_item.message)
        except BaseException as e:
            if sys.version_info.major == 3:
                exc = _ExceptionWithTraceback(e, e.__traceback__)
            else:
                exc = e  # python2 hack
            _result_queue.put(_ResultItem(
                call_item.work_id, exception=exc))
        else:
            _result_queue.put(_ResultItem(
                call_item.work_id, result=r))


class _WorkItem(object):
    def __init__(self, future, message):
        self.future = future
        self.message = message


class _CallItem(object):
    def __init__(self, work_id, message):
        self.work_id = work_id
        self.message = message


def _add_call_item_to_queue(pending_work_items,
                            work_ids,
                            call_queue):
    """Fills call_queue with _WorkItems from pending_work_items.

    This function never blocks.

    Args:
        pending_work_items: A dict mapping work ids to _WorkItems e.g.
            {5: <_WorkItem...>, 6: <_WorkItem...>, ...}
        work_ids: A queue.Queue of work ids e.g. Queue([5, 6, ...]). Work ids
            are consumed and the corresponding _WorkItems from
            pending_work_items are transformed into _CallItems and put in
            call_queue.
        call_queue: A multiprocessing.Queue that will be filled with _CallItems
            derived from _WorkItems.
    """
    while True:
        if call_queue.full():
            return
        try:
            work_id = work_ids.get(block=False)
        except queue.Empty:
            return
        else:
            work_item = pending_work_items[work_id]

            if work_item.future.set_running_or_notify_cancel():
                call_queue.put(_CallItem(work_id,
                                         work_item.message),
                               block=True)
            else:
                del pending_work_items[work_id]
                continue


if sys.version_info.major >= 3:
    # Normal python3 version

    def _queue_management_worker(executor_reference,
                                 _manager,
                                 pending_work_items,
                                 work_ids_queue,
                                 _call_queue,
                                 _result_queue):
        """Manages the communication between this process and the worker processes."""
        executor = None

        def shutting_down():
            return process._shutdown or executor is None or executor._shutdown_thread

        def shutdown_worker():
            # This is an upper bound
            if _manager.is_alive():
                _call_queue.put_nowait(None)
            # Release the queue's resources as soon as possible.
            _call_queue.close()
            # If .join() is not called on the created processes then
            # some multiprocessing.Queue methods may deadlock on Mac OS X.
            _manager.join()

        reader = _result_queue._reader

        while True:
            _add_call_item_to_queue(pending_work_items,
                                    work_ids_queue,
                                    _call_queue)

            sentinel = _manager.sentinel
            assert sentinel
            ready = wait([reader, sentinel])
            if reader in ready:
                result_item = reader.recv()
            else:
                # Mark the process pool broken so that submits fail right now.
                executor = executor_reference()
                if executor is not None:
                    executor._broken = True
                    executor._shutdown_thread = True
                    executor = None
                # All futures in flight must be marked failed
                for work_id, work_item in pending_work_items.items():
                    work_item.future.set_exception(
                        BrokenProcessPool(
                            "A process in the process pool was "
                            "terminated abruptly while the future was "
                            "running or pending."
                        ))
                    # Delete references to object. See issue16284
                    del work_item
                # pending_work_items.clear()
                del pending_work_items[:]
                # Terminate remaining workers forcibly: the queues or their
                # locks may be in a dirty state and block forever.
                _manager.terminate()
                shutdown_worker()
                return
            if isinstance(result_item, int):
                # Clean shutdown of a worker using its PID
                # (avoids marking the executor broken)
                assert shutting_down()
                _manager.join()
                if _manager is None:
                    shutdown_worker()
                    return
            elif result_item is not None:
                work_item = pending_work_items.pop(result_item.work_id, None)
                # work_item can be None if another process terminated (see above)
                if work_item is not None:
                    if result_item.exception:
                        work_item.future.set_exception(result_item.exception)
                    else:
                        work_item.future.set_result(result_item.result)
                    # Delete references to object. See issue16284
                    del work_item
            # Check whether we should start shutting down.
            executor = executor_reference()
            # No more work items can be added if:
            #   - The interpreter is shutting down OR
            #   - The executor that owns this worker has been collected OR
            #   - The executor that owns this worker has been shutdown.
            if shutting_down():
                try:
                    # Since no new work items can be added, it is safe to shutdown
                    # this thread if there are no pending work items.
                    if not pending_work_items:
                        shutdown_worker()
                        return
                except queue.Full:
                    # This is not a problem: we will eventually be woken up (in
                    # _result_queue.get()) and be able to send a sentinel again.
                    pass
            executor = None
else:
    # Compatibility with the python 2 backport
    def _queue_management_worker(executor_reference, _manager,
                                 pending_work_items, work_ids_queue,
                                 _call_queue, _result_queue):
        nb_shutdown_processes = [0]
        def shutdown_one_process():
            """Tell a worker to terminate, which will in turn wake us again"""
            _call_queue.put(None)
            nb_shutdown_processes[0] += 1
        while True:
            _add_call_item_to_queue(pending_work_items,
                                    work_ids_queue,
                                    _call_queue)

            result_item = _result_queue.get(block=True)
            if result_item is not None:
                work_item = pending_work_items[result_item.work_id]
                del pending_work_items[result_item.work_id]

                if result_item.exception:
                    work_item.future.set_exception(result_item.exception)
                else:
                    work_item.future.set_result(result_item.result)
                # Delete references to object. See issue16284
                del work_item
            # Check whether we should start shutting down.
            executor = executor_reference()
            # No more work items can be added if:
            #   - The interpreter is shutting down OR
            #   - The executor that owns this worker has been collected OR
            #   - The executor that owns this worker has been shutdown.
            if process._shutdown or executor is None or executor._shutdown_thread:
                # Since no new work items can be added, it is safe to shutdown
                # this thread if there are no pending work items.
                if not pending_work_items:
                    while nb_shutdown_processes[0] < 1:
                        shutdown_one_process()
                    # If .join() is not called on the created processes then
                    # some multiprocessing.Queue methods may deadlock on Mac OS
                    # X.
                    _manager.join()
                    _call_queue.close()
                    return
            del executor


class ProcessActorExecutor(_base_actor.ActorExecutor):

    def __init__(self, _ActorClass, *args, **kwargs):
        process._check_system_limits()

        self._ActorClass = _ActorClass
        # self._call_queue = multiprocessing.JoinableQueue()
        # If we want to cancel futures we need to give the task_queue a maximum
        # size
        self._call_queue = multiprocessing.Queue(1)
        self._call_queue._ignore_epipe = True
        self._result_queue = multiprocessing.Queue()
        self._work_ids = queue.Queue()
        self._queue_management_thread = None

        # We only maintain one process for our actor
        self._manager = None

        # Shutdown is a two-step process.
        self._shutdown_thread = False
        self._shutdown_lock = threading.Lock()
        self._broken = False
        self._queue_count = 0
        self._pending_work_items = {}

        self._did_initialize = False

        if args or kwargs:
            # If given actor initialization args we must start the Actor
            # immediately. Otherwise just wait until we get a message
            print('Init with args')
            print('args = %r' % (args,))
            self._initialize_actor(*args, **kwargs)

    def post(self, message):
        with self._shutdown_lock:
            if self._broken:
                raise BrokenProcessPool(
                    'A child process terminated '
                    'abruptly, the process pool is not usable anymore')
            if self._shutdown_thread:
                raise RuntimeError('cannot schedule new futures after shutdown')

            f = _base.Future()
            w = _WorkItem(f, message)

            self._pending_work_items[self._queue_count] = w
            self._work_ids.put(self._queue_count)
            self._queue_count += 1
            # Wake up queue management thread
            self._result_queue.put(None)

            self._start_queue_management_thread()
            return f
    post.__doc__ = _base_actor.ActorExecutor.post.__doc__

    def _start_queue_management_thread(self):
        # When the executor gets lost, the weakref callback will wake up
        # the queue management thread.

        def weakref_cb(_, q=self._result_queue):
            q.put(None)

        if self._queue_management_thread is None:
            # Start the processes so that their sentinel are known.
            self._initialize_actor()
            self._queue_management_thread = threading.Thread(
                    target=_queue_management_worker,
                    args=(weakref.ref(self, weakref_cb),
                          self._manager,
                          self._pending_work_items,
                          self._work_ids,
                          self._call_queue,
                          self._result_queue))
            self._queue_management_thread.daemon = True
            self._queue_management_thread.start()
            # use structures already in futures as much as possible
            process._threads_queues[self._queue_management_thread] = self._result_queue

    def _initialize_actor(self, *args, **kwargs):
        if self._manager is None:
            assert self._did_initialize is False, 'only initialize actor once'
            self._did_initialize = True
            # We only maintain one thread process for an actor
            self._manager = multiprocessing.Process(
                    target=_process_actor_eventloop,
                    args=(self._call_queue,
                          self._result_queue, self._ActorClass) + args,
                    kwargs=kwargs)
            self._manager.start()

    def shutdown(self, wait=True):
        with self._shutdown_lock:
            self._shutdown_thread = True
        if self._queue_management_thread:
            # Wake up queue management thread
            self._result_queue.put(None)
            if wait:
                self._queue_management_thread.join()
        # To reduce the risk of opening too many files, remove references to
        # objects that use file descriptors.
        self._queue_management_thread = None
        self._call_queue = None
        self._result_queue = None
        self._manager = None
    shutdown.__doc__ = _base.Executor.shutdown.__doc__


class ProcessActor(_base_actor.Actor):

    @classmethod
    def executor(cls, *args, **kwargs):
        return ProcessActorExecutor(cls, *args, **kwargs)
    # executor.__doc__ = _base_actor.Actor.executor.__doc___

# ProcessActor.__doc__ = _base_actor.Actor.__doc___
