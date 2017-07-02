import futures_actors
from concurrent import futures


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
        if action == 'hello world':
            content = 'hello world'
            return content
        elif action == 'debug':
            return actor
        elif action == 'wait':
            import time
            num = message.get('time', 0)
            time.sleep(num)
            return num
        elif action == 'prime':
            import ubelt as ub
            a = actor.state['a']
            n = message['n']
            return n, a, ub.find_nth_prime(n + a)
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

    print('-----------------')
    print('Simple test of {}'.format(ActorClass))

    test_state = {'done': False}

    def done_callback(result):
        test_state['done'] = True
        print('result = %r' % (result,))
        print('DOING DONE CALLBACK')

    print('Starting Test')
    executor = ActorClass.executor()
    print('About to send messages')

    f1 = executor.post({'action': 'hello world'})
    print(f1.result())

    f2 = executor.post({'action': 'start'})
    print(f2.result())

    f3 = executor.post({'action': 'add'})
    print(f3.result())

    print('Test completed')
    print('L______________')


def test_callbacks(ActorClass, F=0.01):
    """
    F is a  Factor to control wait time

    CommandLine:
        python -m futures_actors.tests test_callbacks:1

    Example:
        >>> from futures_actors.tests import *  # NOQA
        >>> try:
        >>>     test_callbacks(TestProcessActor, F=1.0)
        >>> except AssertionError as ex:
        >>>     # If it fails once on the fast setting try
        >>>     # once more on a slower setting (for travis python 2.7)
        >>>     print(ex)
        >>>     print('Failed the fast version. Try once more, but slower')
        >>>     test_callbacks(TestProcessActor, F=2.0)

    Example:
        >>> from futures_actors.tests import *  # NOQA
        >>> try:
        >>>     test_callbacks(TestThreadActor, F=1.0)
        >>> except AssertionError as ex:
        >>>     print(ex)
        >>>     # If it fails once on the fast setting try
        >>>     # once more on a slower setting (for travis python 2.7)
        >>>     print('Failed the fast version. Try once more, but slower')
        >>>     test_callbacks(TestThreadActor, F=2.0)
    """
    print('-----------------')
    print('Test callbacks for {}'.format(ActorClass))

    test_state = {'num': False}

    def done_callback(f):
        num = f.result()
        test_state['num'] += num
        print('DONE CALLBACK GOT = {}'.format(num))

    executor = ActorClass.executor()
    print('Submit task 1')
    f1 = executor.post({'action': 'wait', 'time': 1 * F})
    f1.add_done_callback(done_callback)

    print('Submit task 2')
    f2 = executor.post({'action': 'wait', 'time': 2 * F})
    f2.add_done_callback(done_callback)

    print('Submit task 3')
    f3 = executor.post({'action': 'wait', 'time': 3 * F})
    f3.add_done_callback(done_callback)

    # Should reach this immediately before any task is done
    num = test_state['num']
    assert num == 0 * F, 'should not have finished any task yet. got num={}'.format(num)

    # Wait for the second result
    print(f2.result())
    num = test_state['num']
    assert num == 3 * F, 'should have finished task 1 and 2. got num={}'.format(num)

    # Wait for the third result
    print(f3.result())
    num = test_state['num']
    assert num == 6 * F, 'should have finished all tasks. got num={}'.format(num)

    print('Test completed')
    print('L______________')


def test_cancel(ActorClass, F=0.01):
    """
    F is a factor to control wait time

    CommandLine:
        python -m futures_actors.tests test_cancel

    Example:
        >>> from futures_actors.tests import *  # NOQA
        >>> try:
        >>>     test_cancel(TestProcessActor, F=0.01)
        >>> except AssertionError as ex:
        >>>     print(ex)
        >>>     # If it fails once on the fast setting try
        >>>     # once more on a slower setting (for travis python 2.7)
        >>>     print('!Failed the fast version. Try once more, but slower')
        >>>     test_cancel(TestProcessActor, F=2.0)
        >>>     print('Slower version worked')

    Example:
        >>> from futures_actors.tests import *  # NOQA
        >>> try:
        >>>     test_cancel(TestThreadActor, F=1.0)
        >>> except AssertionError as ex:
        >>>     print(ex)
        >>>     # If it fails once on the fast setting try
        >>>     # once more on a slower setting (for travis python 2.7)
        >>>     print('!Failed the fast version. Try once more, but slower')
        >>>     test_cancel(TestThreadActor, F=2.0)
        >>>     print('Slower version worked')

    """
    print('-----------------')
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

    executor = ActorClass.executor()
    print('Submit task 1')
    f1 = executor.post({'action': 'wait', 'time': 1 * F})
    f1.add_done_callback(done_callback)

    print('Submit task 2')
    f2 = executor.post({'action': 'wait', 'time': 2 * F})
    f2.add_done_callback(done_callback)

    print('Submit task 3')
    f3 = executor.post({'action': 'wait', 'time': 3 * F})
    f3.add_done_callback(done_callback)

    print('Submit task 4')
    f4 = executor.post({'action': 'wait', 'time': 4 * F})
    f4.add_done_callback(done_callback)

    can_cancel = f3.cancel()
    # print('can_cancel = %r' % (can_cancel,))
    assert can_cancel, 'we should be able to cancel in time'

    f1.result()
    f2.result()
    f4.result()
    num = test_state['num']
    assert num == 7 * F, 'f3 was not cancelled. got num={}'.format(num)

    print('Test completed')
    print('L______________')


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
    f1 = ex1.post({'action': 'add'})
    assert f1.result()[1] == 1000 + 64


def test_multiple(ActorClass):
    """
    Example:
        >>> from futures_actors.tests import *  # NOQA
        >>> test_multiple(TestProcessActor)

    Example:
        >>> from futures_actors.tests import *  # NOQA
        >>> test_multiple(TestThreadActor)
    """
    print('-----------------')
    print('Test multiple for {}'.format(ActorClass))
    # Make multiple actors and send them each multiple jobs
    n_actors = 5
    n_jobs = 10
    actors_exs = [ActorClass.executor(a) for a in range(1, n_actors)]
    fs = []
    for jobid in range(n_jobs):
        n = jobid + 500
        fs += [ex.post({'action': 'prime', 'n': n}) for ex in actors_exs]

    for f in futures.as_completed(fs):
        print('n, a, prime = {}'.format(f.result()))

    actors = [ex.post({'action': 'debug'}).result() for ex in actors_exs]
    for a in actors:
        print(a.state)
    print('Test completed')
    print('L______________')


# def main():
#     """
#     Ignore:
#         ActorClass = TestProcessActor
#         ActorClass = TestThreadActor

#     Example:
#         >>> from futures_actors import tests
#         >>> tests.main()
#     """
#     classes = [
#         TestProcessActor,
#         TestThreadActor,
#     ]
#     for ActorClass in classes:
#         test_multiple(ActorClass)
#         test_actor_args(ActorClass)
#         test_simple(ActorClass)
#         test_callbacks(ActorClass)
#         test_cancel(ActorClass)

if __name__ == '__main__':
    r"""
    CommandLine:
        python -m futures_actors.tests all --verbose
    """
    import ubelt as ub  # NOQA
    ub.doctest_package()
