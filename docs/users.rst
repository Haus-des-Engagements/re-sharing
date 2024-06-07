 .. _users:

Users
======================================================================

Starting a new project, it’s highly recommended to set up a custom user model,
even if the default User model is sufficient for you.

This model behaves identically to the default user model,
but you’ll be able to customize it in the future if the need arises.


A user can be part of an organization. Only organizations can book a room.
A user can have different roles in an organization: admin, booker

.. automodule:: roomsharing.users.models
   :members:
   :noindex:

