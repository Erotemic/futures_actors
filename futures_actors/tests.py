import futures_actors
from concurrent import futures
import ubelt as ub
from os.path import join, exists


class TestActorMixin(object):
    """
    An actor is given messages from its manager and performs actions in a
    single thread. Its state is private and threadsafe.

    The handle method must be implemented by the user.
    """
    def __init__(actor, a=None, factor=1):
        actor.state = {}
        if a is not None:
            actor.state['a'] = a * factor

    def handle(actor, message):
        print('handling message = {}'.format(message))
        if not isinstance(message, dict):
            raise ValueError('Commands must be passed in a message dict')
        message = message.copy()
        action = message.pop('action', None)
        if action is None:
            raise ValueError('message must have an action item')
        elif action == 'hello world':
            content = 'hello world'
            return content
        elif action == 'lockfile':
            fpath = message['fpath']
            num = message['num']
            while not exists(fpath):
                pass
            return num
        elif action == 'debug':
            return actor
        elif action == 'prime':
            import ubelt as ub
            a = actor.state['a']
            n = message['n']
            return n, a, ub.find_nth_prime(n + a)
        elif action == 'exception':
            raise Exception('Oops')
        elif action == 'start':
            actor.state['a'] = 3
            return 'started'
        elif action == 'add':
            for i in range(1000):
                actor.state['a'] += 1
            return 'added', actor.state['a']
        else:
            raise ValueError('Unknown action=%r' % (action,))


class TestProcessActor(TestActorMixin, futures_actors.ProcessActor):
    pass


class TestThreadActor(TestActorMixin, futures_actors.ThreadActor):
    pass


def test_simple(ActorClass):
    """
    Example:
        >>> from futures_actors.tests import *  # NOQA
        >>> test_simple(TestProcessActor)

    Example:
        >>> from futures_actors.tests import *  # NOQA
        >>> test_simple(TestThreadActor)
    """
    # from actor2 import *
    # from actor2 import _add_call_item_to_queue, _queue_management_worker
    print('Simple test of {}'.format(ActorClass))

    print('Starting Test')
    with ActorClass.executor() as executor:
        print('About to send messages')

        f1 = executor.post({'action': 'hello world'})
        print(f1.result())

        f2 = executor.post({'action': 'start'})
        print(f2.result())

        f3 = executor.post({'action': 'add'})
        print(f3.result())


def test_callbacks(ActorClass, F=0.01):
    """
    F is a  Factor to control wait time

    CommandLine:
        python -m futures_actors.tests test_callbacks:1

    Example:
        >>> from futures_actors.tests import *  # NOQA
        >>> try:
        >>>     test_callbacks(TestProcessActor, F=0.1)
        >>> except AssertionError as ex:
        >>>     # If it fails once on the fast setting try
        >>>     # once more on a slower setting (for travis python 2.7)
        >>>     print(ex)
        >>>     print('Failed the fast version. Try once more, but slower')
        >>>     test_callbacks(TestProcessActor, F=2.0)

    Example:
        >>> from futures_actors.tests import *  # NOQA
        >>> try:
        >>>     test_callbacks(TestThreadActor, F=0.1)
        >>> except AssertionError as ex:
        >>>     print(ex)
        >>>     # If it fails once on the fast setting try
        >>>     # once more on a slower setting (for travis python 2.7)
        >>>     print('Failed the fast version. Try once more, but slower')
        >>>     test_callbacks(TestThreadActor, F=2.0)
    """
    print('Test callbacks for {}'.format(ActorClass))

    import shutil
    print('Test cancel for {}'.format(ActorClass))

    test_state = {'num': 0}
    def done_callback(f):
        num = f.result()
        test_state['num'] += num
        print('DONE CALLBACK GOT = {}'.format(num))

    cache_dpath = ub.ensure_app_cache_dir('futures_actors', 'tests')
    shutil.rmtree(cache_dpath)
    ub.ensuredir(cache_dpath)

    fpaths = [join(cache_dpath, 'lock{}'.format(i)) for i in range(0, 5)]

    executor = ActorClass.executor()
    try:
        print('Submit task 1')
        f1 = executor.post({'action': 'lockfile', 'num': 1, 'fpath': fpaths[1]})
        f1.add_done_callback(done_callback)

        print('Submit task 2')
        f2 = executor.post({'action': 'lockfile', 'num': 2, 'fpath': fpaths[2]})
        f2.add_done_callback(done_callback)

        print('Submit task 3')
        f3 = executor.post({'action': 'lockfile', 'num': 3, 'fpath': fpaths[3]})
        f3.add_done_callback(done_callback)

        # Should reach this immediately before any task is done
        num = test_state['num']
        assert num == 0, 'should not have finished any task yet. got num={}'.format(num)

        # Unblock task2, but task1 should still be blocking it
        print('unblock task2')
        ub.touch(fpaths[2])
        import time
        time.sleep(.01)
        num = test_state['num']
        assert num == 0, 'should be blocked by task1. got num={}'.format(num)

        # Unblock task1
        print('unblock task1')
        ub.touch(fpaths[1])
        # Wait for the second result
        print(f2.result())
        assert f1.done(), 'first task should be done'
        num = test_state['num']
        assert num == 3, 'should have finished task 1 and 2. got num={}'.format(num)

        # Wait for the third result
        print('unblock task3')
        ub.touch(fpaths[3])
        print(f3.result())
        num = test_state['num']
        assert num == 6, 'should have finished 3 tasks. got num={}'.format(num)
    finally:
        print('shutdown executor')
        executor.shutdown(wait=False)

    shutil.rmtree(cache_dpath)


def test_cancel(ActorClass, F=0.01):
    """
    F is a factor to control wait time

    CommandLine:
        python -m futures_actors.tests test_cancel:0
        python -m futures_actors.tests test_cancel:1

    Ignore:
        from futures_actors.tests import *  # NOQA
        ActorClass = TestProcessActor

    Example:
        >>> from futures_actors.tests import *  # NOQA
        >>> test_cancel(TestProcessActor)

    Example:
        >>> from futures_actors.tests import *  # NOQA
        >>> test_cancel(TestThreadActor)
    """
    import shutil
    print('Test cancel for {}'.format(ActorClass))

    test_state = {'num': False}
    def done_callback(f):
        try:
            num = f.result()
        except futures.CancelledError:
            num = 'canceled'
            print('Canceled task {}'.format(f))
        else:
            test_state['num'] += num
            print('DONE CALLBACK GOT = {}'.format(num))

    cache_dpath = ub.ensure_app_cache_dir('futures_actors', 'tests')
    shutil.rmtree(cache_dpath)
    ub.ensuredir(cache_dpath)

    fpaths = [join(cache_dpath, 'lock{}'.format(i)) for i in range(0, 5)]

    executor = ActorClass.executor()
    try:
        print('Submit task 1')
        f1 = executor.post({'action': 'lockfile', 'num': 1, 'fpath': fpaths[1]})
        f1.add_done_callback(done_callback)

        print('Submit task 2')
        f2 = executor.post({'action': 'lockfile', 'num': 2, 'fpath': fpaths[2]})
        f2.add_done_callback(done_callback)

        print('Submit task 3')
        f3 = executor.post({'action': 'lockfile', 'num': 3, 'fpath': fpaths[3]})
        f3.add_done_callback(done_callback)

        print('Submit task 4')
        f4 = executor.post({'action': 'lockfile', 'num': 4, 'fpath': fpaths[4]})
        f4.add_done_callback(done_callback)

        can_cancel = f3.cancel()
        assert can_cancel, 'we should be able to cancel in time'

        # Write the files to unlock the processes
        for f in fpaths:
            ub.touch(f)

        f1.result()
        f2.result()
        f4.result()
    finally:
        executor.shutdown(wait=True)

    num = test_state['num']
    assert num == 7, 'f3 was not cancelled. got num={}'.format(num)

    shutil.rmtree(cache_dpath)


def test_actor_args(ActorClass):
    """
    Example:
        >>> from futures_actors.tests import *  # NOQA
        >>> test_actor_args(TestProcessActor)

    Example:
        >>> from futures_actors.tests import *  # NOQA
        >>> test_actor_args(TestThreadActor)
    """
    ex1 = ActorClass.executor(8, factor=8)
    try:
        f1 = ex1.post({'action': 'add'})
        assert f1.result()[1] == 1000 + 64
    finally:
        ex1.shutdown(wait=True)


def test_multiple(ActorClass):
    """
    Example:
        >>> from futures_actors.tests import *  # NOQA
        >>> test_multiple(TestProcessActor)

    Example:
        >>> from futures_actors.tests import *  # NOQA
        >>> test_multiple(TestThreadActor)
    """
    print('Test multiple for {}'.format(ActorClass))
    # Make multiple actors and send them each multiple jobs
    n_actors = 5
    n_jobs = 10
    actors_exs = [ActorClass.executor(a) for a in range(1, n_actors)]
    try:
        fs = []
        for jobid in range(n_jobs):
            n = jobid + 200
            fs += [ex.post({'action': 'prime', 'n': n}) for ex in actors_exs]

        for f in futures.as_completed(fs):
            print('n, a, prime = {}'.format(f.result()))

        actors = [ex.post({'action': 'debug'}).result() for ex in actors_exs]
        for a in actors:
            print(a.state)
    finally:
        for ex in actors_exs:
            ex.shutdown(wait=True)


def test_exception(ActorClass):
    """
    CommandLine:
        python -m futures_actors.tests test_exception
        python -m futures_actors.tests test_exception:0
        python -m futures_actors.tests test_exception:1

    Ignore:
        from futures_actors.tests import *  # NOQA
        ActorClass = TestProcessActor

    Example:
        >>> from futures_actors.tests import *  # NOQA
        >>> test_exception(TestProcessActor)

    Example:
        >>> from futures_actors.tests import *  # NOQA
        >>> test_exception(TestThreadActor)
    """
    with ActorClass.executor() as executor:
        print('Submit task 1')
        f1 = executor.post({'action': 'exception'})

        while not f1.done():
            pass
        print('f1 is done')

        try:
            f1.result()
        except Exception as ex:
            print('Correctly got exception = {}'.format(repr(ex)))
        else:
            raise AssertionError('should have gotten an exception')


if __name__ == '__main__':
    r"""
    CommandLine:
        python -m futures_actors.tests all --verbose
    """
    import ubelt as ub  # NOQA
    ub.doctest_package()
