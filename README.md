An extension of the python concurrent.futures module to support stateful computations using a simplified actor model. 


### Purpose
Allows a class to be created in a separate thread/process.
Unlike the simple functions that can be run using the builtin concurrent.futures module, the class instance can
  maintain its own private state.
Messages (in the form of arbitrary pickleable objects) can be send to this process allowing communication.
The actor responds in the form of a Future object.

### API
There are two main attributes exposed:
`futures_utils.ThreadActor` and `futures_utils.ProcessActor`.
Each of this are abstract base classes that a custom actor class should inherit from.
This custom class should implement a `handles(self, message)` method, which should accept an arbitrary message
  object and can return arbitrary responses.
To get asynchronous computation, a new instance should be created using the `executor(*args, **kw)` method, which
  will call the constructor of the class in a separate thread/process and return an `executor` object that can be
  used to send messages to it.
This `executor` object works very similar to a  `concurrent.futures.ThreadExecutor` or
  `concurrent.futures.ProcessExecutor`, except instead of having a `submit(func, *args, **kw)` method that takes a
  function and arguments, it has a `post(message)` method that sends a message to the asynchronous actor.
However, like `submit`, `post` also returns a `Future` object.


### Example

```python
from futures_actors import ThreadActor
class MyActor(ThreadActor):
    def __init__(self):
        self.state = 5
    #
    def handle(self, message):
        self.state += message
        return self.state
#
executor = MyActor.executor()
f = executor.post(10)
assert f.result() == 15
```





### Limitations
Currently actors can only communicate with their executor. Simple support for
actors communicating with other actors is not supported.


#### Implementation details
Most of this code is duplicated from the concurrent.futures.thread and
concurrent.futures.process modules, written by Brian Quinlan. The main
difference is that we expose an `Actor` class which can be inherited from and
provides the `executor` classmethod. This creates an asynchronously maintained
instance of this class in a separate thread/process

