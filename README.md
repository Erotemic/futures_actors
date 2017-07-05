[![Travis](https://img.shields.io/travis/Erotemic/futures_actors.svg)](https://travis-ci.org/Erotemic/futures_actors)
[![Pypi](https://img.shields.io/pypi/v/futures_actors.svg)](https://pypi.python.org/pypi/futures_actors)
[![Codecov](https://codecov.io/github/Erotemic/futures_actors/badge.svg?branch=master&service=github)](https://codecov.io/github/Erotemic/futures_actors?branch=master)

An extension of the concurrent.futures module to support stateful computations using a simplified actor model. 


## Purpose
Allows a class to be created in a separate thread/process.
Unlike the simple functions that can be run using the builtin concurrent.futures module, the class instance can
  maintain its own private state.
Messages (in the form of arbitrary pickleable objects) can be send to this process allowing communication.
The actor responds in the form of a Future object.

## Installation:

You can install the latest stable version through pypi.
```
pip install futures_actors
```

Or you can install the latest development version through GitHub.
```
pip install git+https://github.com/Erotemic/futures_actors.git
```


## API
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

Here is a simple example showing basic usage 

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


Here is another setting multiple messages at once, cancelling a task, and
adding callbacks.


```python
import futures_actors

class TestActor(futures_actors.ProcessActor):
    def __init__(actor, a=None, factor=1):
        actor.state = {}
        if a is not None:
            print('init mixin with args')
            print('a = %r' % (a,))
            actor.state['a'] = a * factor

    def handle(actor, message):
        print('handling message = {}'.format(message))
        if not isinstance(message, dict):
            raise ValueError('Commands must be passed in a message dict')
        message = message.copy()
        action = message.pop('action', None)
        if action is None:
            raise ValueError('message must have an action item')
        if action == 'debug':
            return actor
        if action == 'wait':
            import time
            num = message.get('time', 0)
            time.sleep(num)
            return num
        else:
            raise ValueError('Unknown action=%r' % (action,))

test_state = {'num': False}

def done_callback(f):
    """ this will be executed in the main process """
    try:
        num = f.result()
    except futures.CancelledError:
        num = 'canceled'
        print('Canceled task {}'.format(f))
    else:
        test_state['num'] += num
        print('DONE CALLBACK GOT = {}'.format(num))

executor = TestActor.executor()
f1 = executor.post({'action': 'wait', 'time': 1})
f1.add_done_callback(done_callback)

f2 = executor.post({'action': 'wait', 'time': 2})
f2.add_done_callback(done_callback)

f3 = executor.post({'action': 'wait', 'time': 3})
f3.add_done_callback(done_callback)

f4 = executor.post({'action': 'wait', 'time': 4})
f4.add_done_callback(done_callback)

can_cancel = f3.cancel()
assert can_cancel, 'we should be able to cancel in time'

f4.result()
assert test_state['num'] == 7, 'f3 was not cancelled'
```



## Limitations
Currently actors can only communicate with their executor. Simple support for
actors communicating with other actors is not supported.


### Implementation details
Most of this code is duplicated from the concurrent.futures.thread and
concurrent.futures.process modules, written by Brian Quinlan. The main
difference is that we expose an `Actor` class which can be inherited from and
provides the `executor` classmethod. This creates an asynchronously maintained
instance of this class in a separate thread/process

