"""
TODO:
    Actors need to be able to reference each other.
        * this means we need to be able to pass a reference
          that can post a message to an actor's executor.
    Actors need to be able to create more actors.
        * This should be fairly simple if the first task is complete.

    Idea:
        maintain a list of weakreferences to all actor executors ever created
        in a thread. Actors must have a way of interacting with this thread.

"""

from concurrent.futures import _base


class ActorExecutor(_base.Executor):
    """
    Executor to manage exactly one actor.

    This class lives in the main thread, manages a process containing exactly
    one Actor, and is used to send messages to that actor. Responses are
    returned in the form of a `Future` object.
    """

    def post(self, message):  # nocover
        """
        analagous to _base.Executor.submit, but sends a message to the actor
        controlled by this Executor, and returns a Future.
        """
        raise NotImplementedError(
            'use ProcessActorExecutor or ThreadActorExecutor')  # nocover


class Actor(object):
    """
    Base actor class.

    Actors receive messages, which are arbitrary objects from their managing
    executor.

    The `Actor` class can be inherited from and provides the `executor`
    classmethod. This creates an asynchronously maintained instance of this
    class in a separate thread/process

    Example:
        >>> from futures_actors import ThreadActor
        >>> class MyActor(ThreadActor):
        >>>     def __init__(self):
        >>>         self.state = 5
        >>>     #
        >>>     def handle(self, message):
        >>>         self.state += message
        >>>         return self.state
        >>> #
        >>> executor = MyActor.executor()
        >>> f = executor.post(10)
        >>> assert f.result() == 15
    """
    @classmethod
    def executor(cls):  # nocover
        """
        Creates an asychronous instance of this Actor and returns the executor
        to manage it.
        """
        raise NotImplementedError('use ProcessActor or ThreadActor')  # nocover

    def handle(self, message):  # nocover
        """
        This method recieves, handles, and responds to the messages sent from
        the executor. This function can return arbitrary values. These values
        can be accessed from the main thread using the Future object returned
        when the message was posted to this actor by the executor.
        """
        raise NotImplementedError('must implement message handler')  # nocover
