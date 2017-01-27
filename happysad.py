# coding=utf-8
"""
Black magic metaprogramming to redefine descriptors in python instances.
You should never lie, avoid to use this if possible.
When using it, you should really understand what you are doing.
You will probably also need paracetamol.

These patched objects have two personalities, or more concretely, two classes.
One is their original class, when exposing it objects are "sad".
The other one is an instance specific subclass, when exposing it objects are "happy".
(just funny API)

TODO... write proper doc and tests

Pickling
--------
Mixing liars dark magic with object serialization / pickling is not a good idea.
You can either use dill or temporarilly pickle using

>>> import pickle
>>> inst = 2
>>> with forget_synthetic_class(inst):
...     pickle.dumps(inst)

In our use case, serialization was handled by pickle only after
storing the important stuff in a dictionary.

Using these functions you can control access to members of objects when
you do not want to, or cannot, touch their code, and overriding or simple
attribute setting would not be enough.

We use this magic at loopbio to modify the behavior of layers in deep neural networks
from (heavily designed) frameworks, hoping for minimal maintenance costs on our
side. Thanks to them we are able to correct performance deficits and bugs in these
frameworks.
"""
from __future__ import print_function, division

from contextlib import contextmanager

__author__ = 'Santi Villalba'
__version__ = '0.1.0'
__license__ = '3-clause BSD'

__all__ = ['happy', 'make_happy', 'maybe_happy',
           'sad', 'make_sad',
           'saddest',
           'RetrievableDescriptor', 'MemberView', 'ControlledSetter',
           'take_happy_pills', 'create_with_joy']


# --- Synthetic/Original classes swapping

# noinspection PyProtectedMember
def _original_class(inst):
    """Returns `inst` original class, without any class swapping."""
    try:
        return inst._Xoriginal_classX
    except AttributeError:
        return inst.__class__


# noinspection PyProtectedMember
def _synthetic_class(inst):
    """Returns `inst` synthetic class (can be None), without any swapping."""
    try:
        return inst._Xsynthetic_classX
    except AttributeError:
        return None


def _bookkept_attrs(inst):
    """Returns the dictionary of synthetic class bookkept attributes."""
    return _synthetic_class(inst).bookeeping


def _delete_old_attrs(inst):
    """Deletes the synthetic class bookkept attributes from the instance."""
    if inst.__class__ == _original_class(inst):
        bookkept = _bookkept_attrs(inst)
        for attr in bookkept:
            try:
                bookkept[attr] = getattr(inst, attr)
                delattr(inst, attr)
            except AttributeError:
                pass


def _set_synthetic(inst):
    """
    Mutates the instance to be of the synthetic class.
    Takes care of storing away the bookkept attributes.
    """
    _delete_old_attrs(inst)
    inst.__class__ = _synthetic_class(inst)


def _reset_old_attrs(inst):
    """Sets the synthetic class bookkept attributes in the instance."""
    if inst.__class__ == _original_class(inst):
        for attr, val in _bookkept_attrs(inst).items():
            setattr(inst, attr, val)


def _set_original(inst):
    """
    Mutates the instance to be of the original class.
    Takes care of restoring the bookkept attributes.
    """
    inst.__class__ = _original_class(inst)
    _reset_old_attrs(inst)


def _create_synthetic_class(cls):
    """Creates a synthetic subclass of cls, adding a few attributes."""
    # Python 2, old style classes support
    if not isinstance(cls, type):
        cls = type(cls.__name__, (cls, object), {})
    # Create the subclass
    return type(cls.__name__, (cls,), {'XsyntheticX': True,
                                       'bookeeping': {}})


# noinspection PyProtectedMember,PyTypeChecker
def force_synthetic_class(inst):
    """
    Derives a synthetic class from `inst` class and assigns it to `inst.__class__`.
    If inst already has a synthetic class in `inst._Xsynthetic_classX`,
    it is used instead of creating a new one.

    In this way any manipulation to the instance class will be local to `inst`.

    The original class can be retrieved by `inst._Xoriginal_classX`.

    The synthetic class has provision for storing old values in the original
    instance by providing a "bookeeping" dictionary. It can be used to provide
    "undo" / "redo" abilities to other monkey-patching pals.

    Parameters
    ----------
    inst : object
      Any object we want to make its class local to.

    Returns
    -------
    The synthetic class of the object (i.e. its current class, for fluency).
    """
    if not hasattr(inst, '_Xsynthetic_classX'):
        inst._Xsynthetic_classX = _create_synthetic_class(type(inst))
        inst._Xoriginal_classX = inst.__class__
        inst.__class__ = inst._Xsynthetic_classX
    _set_synthetic(inst)
    return inst.__class__


def maybe_synthetic_class(inst):
    """
    Attributes inst to its synthetic class if it exists, otherwise does nothing.

    Returns the current class for the instance for fluency.
    """
    try:
        _set_synthetic(inst)
    except AttributeError:
        pass
    return inst.__class__


def force_original_class(inst):
    """
    Forces an instance to use its original class.
    See `force_synthetic_class`.

    Returns the current class for the instance for fluency.
    """
    try:
        _set_original(inst)
    except AttributeError:
        pass
    return inst.__class__


def forget_synthetic_class(inst):
    try:
        force_original_class(inst)
        delattr(inst, '_Xsynthetic_classX')
    except AttributeError:
        pass
    return inst.__class__


def _original_class_contextmanager_factory(forget):
    """
    Generate context managers for setting the original class.

    If forget is False, `force_original_class` is called,
    simply ensuring the object is of the original class in the context.

    If forget is True, `forget_synthetic_class` is called,
    ensuring the object is of the original class in the context
    and temporarily removing the synthetic class attribute.
    This is specially useful to ensure (de)serialization does not
    fail because of the generated classes.
    """

    to_original = force_original_class if not forget else forget_synthetic_class

    @contextmanager
    def cm(inst, *insts):
        insts = (inst,) + insts
        current_classes = [inst.__class__ for inst in insts]
        synth_classes = [_synthetic_class(inst) for inst in insts]
        if len(insts) == 1:
            yield to_original(insts[0])
        else:
            yield tuple(to_original(inst) for inst in insts)
        for current_class, synth_class, inst in zip(current_classes, synth_classes, insts):
            if synth_class is not None:
                inst._Xsynthetic_classX = synth_class
                if current_class == _synthetic_class(inst):
                    force_synthetic_class(inst)

    cm.__name__ = 'original_class' if not forget else 'no_synthetic_class'
    cm.__doc__ = ('Call `%s` in a context manager.' %
                  ('force_original_class' if not forget else 'forget_synthetic_class'))
    return cm

original_class = _original_class_contextmanager_factory(forget=False)
no_synthetic_class = _original_class_contextmanager_factory(forget=True)


@contextmanager
def synthetic_class(inst, *insts):
    """Call `force_synthetic_class` in a context manager."""
    insts = (inst,) + insts
    classes = [inst.__class__ for inst in insts]
    if len(insts) == 1:
        yield force_synthetic_class(insts[0])
    else:
        yield tuple(force_synthetic_class(inst) for inst in insts)
    for cls, inst in zip(classes, insts):
        if cls == _original_class(inst):
            force_original_class(inst)


# --- Descriptors

class RetrievableDescriptor(object):
    """
    An abstract descriptor which allows to retrieve itself and control setting policies.

    Ideally, you will need to override `_get_hook` and `set_hook` in subclasses.

    Parameters
    ----------
    on_set: one of ('pass', 'fail', 'set')
      What to do with the descriptor when set is called.
      If pass: do nothing
      If fail: raise an exception
      If set: call hook method _set_hook()
    """

    def __init__(self, on_set='pass'):
        super(RetrievableDescriptor, self).__init__()
        valid_on_set = 'pass', 'fail', 'set'
        if on_set not in valid_on_set:
            raise ValueError('on_set must be one of %r' % (valid_on_set,))
        self.on_set = on_set

    def __get__(self, instance, owner):
        # Allow to access the descriptor itself via the class
        if instance is None:
            return self
        return self._get_hook(instance, owner)

    def _get_hook(self, instance, owner):
        """Actual implementation of __get__ when it is called on the instance, instead of on the class."""
        raise NotImplementedError()

    def __set__(self, instance, value):
        if self.on_set == 'fail':
            raise Exception('Trying to set a read only constant')
        elif self.on_set == 'set':
            self._set_hook(instance, value)

    def _set_hook(self, instance, value):
        """Actual implementation of __set__ when `self.on_set == 'set'`."""
        raise NotImplementedError()


class MemberView(RetrievableDescriptor):
    """A descriptor that acts as a view to another object member."""
    def __init__(self, viewed_object, parameter, on_set='pass'):
        super(MemberView, self).__init__(on_set=on_set)
        self.viewed_object = viewed_object
        self.parameter = parameter

    def _get_hook(self, _, owner):
        return getattr(self.viewed_object, self.parameter)

    def _set_hook(self, _, value):
        setattr(self.viewed_object, self.parameter, value)


class ControlledSetter(RetrievableDescriptor):
    """A descriptor that can (dis)allow setting and always returns a private variable."""

    def __init__(self, val=None, on_set='pass'):
        super(ControlledSetter, self).__init__(on_set=on_set)
        self.val = val

    def _get_hook(self, *_):
        return self.val

    def _set_hook(self, _, value):
        self.val = value


# Some useful descriptors
AlwaysNone = ControlledSetter(val=None, on_set='pass')
StrictAlwaysNone = ControlledSetter(val=None, on_set='fail')


def add_descriptors(inst, bookkeep_attrs=False, **descriptors):
    """
    Adds descriptors to an object instance class.

    `inst'  is forced to have a local synthetic class first, so the original
     class is untouched (see `force_synthetic_class`). As a side effect, inst
     is mutated to be of the synthetic class.

    Any attribute already in the instance will be deleted. They can be
    saved by setting `save_old` to True. In this case, they will be restablished
    and deleted each time `force_synthetic_class` and `force_original_class` are
    used to cycle through inst synthetic and original classes.

    Returns inst itself for fluency.

    Examples
    --------
    >>> class Mango(object):
    ...     def __init__(self, price=2):
    ...         super(Mango, self).__init__()
    ...         self.price = price
    >>> mango = Mango()
    >>> mango.price
    2
    >>> mango = add_descriptors(mango, bookkeep_attrs=True, price=ControlledSetter(5))
    >>> mango.price
    5
    >>> mango.price = 7
    >>> mango.price
    5
    >>> mango = add_descriptors(mango, price=ControlledSetter(5, on_set='fail'))
    >>> mango.price = 7
    Traceback (most recent call last):
    ...
    Exception: Trying to set a read only constant

    >>> with sad(mango):
    ...     print('Old original price:', mango.price)
    ...     mango.price = 2.5
    ...     print('New original price:', mango.price)
    Old original price: 2
    New original price: 2.5
    >>> mango.price
    5

    >>> with sad(mango):
    ...     print('Old original price:', mango.price)
    Old original price: 2.5

    >>> with happy(mango):
    ...     mango.price
    5
    """
    cls = force_synthetic_class(inst)
    for name, descriptor in descriptors.items():
        try:
            if bookkeep_attrs:
                _bookkept_attrs(inst)[name] = getattr(inst, name)
            delattr(inst, name)
        except AttributeError:
            pass
        setattr(cls, name, descriptor)
    return inst


def class_with_descriptors(cls, **descriptors):
    """Creates a subclass from cls and adds some descriptors to it."""
    # Derive a new class, with the given descriptors
    cls = _create_synthetic_class(cls)
    for name, descriptor in descriptors.items():
        setattr(cls, name, descriptor)
    return cls


def intercept_creation(cls, descriptors, *args, **kwargs):
    """Intercepts attribute access upon instance creation."""
    synthetic = class_with_descriptors(cls, **descriptors)
    inst = synthetic(*args, **kwargs)
    inst._Xsynthetic_classX = synthetic
    inst._Xoriginal_classX = cls
    return inst


# --- Happy/Sad API

make_happy = force_synthetic_class
happy = synthetic_class
maybe_happy = maybe_synthetic_class
make_sad = force_original_class
sad = original_class
make_saddest = forget_synthetic_class
saddest = no_synthetic_class
take_happy_pills = add_descriptors
create_with_joy = intercept_creation
