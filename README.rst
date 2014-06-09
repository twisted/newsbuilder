.. image:: https://badge.waffle.io/twisted/newsbuilder.png?label=ready&title=Ready
 :target: https://waffle.io/twisted/newsbuilder
 :alt: 'Stories in Ready'

Newsbuilder
===========

Newsbuilder let's you avoid merge conflicts in your project's NEWS file, by turning a folder full of ticket news snippets like this:

* *123.bugfix*: Fixed a thing.
* *124.feature*: Added a feature.

Into something like this:

Features:
    Added a feature (#124).
Bugfixes:
    Fixed a thing (#123).


A NEWS file is a text file stored in the top level of your project. It contains descriptions of the bugs, enhancements and miscellaneous changes made in each release.

If authors are allowed to modify the NEWS file directly, though, you will soon encounter spurious conflicts. To avoid this, Newsbuilder uses a scheme involving separate files for each change.

Branch authors write high-level descriptions of their changes into a specially named text file and add it to a `topfiles` directory in the package. Newsbuilder will then aggregate these text files, add the content to the project level NEWS file and delete the original text files. The changes to the project NEWS file can then be reviewed, committed and distributed at each release.

An entry must be a file named <ticket number>.<change type> (eg. 1234.bugfix). You should replace <ticket number> with the ticket number which is being resolved by the change (if multiple tickets are resolved, multiple files with the same contents should be added). The <change type> extension is replaced by one of the following literal strings:

feature
    Tickets which are adding a new feature.

bugfix
    Tickets which are fixing a bug.

doc
    Tickets primarily about fixing or improving documentation (any variety).

removal
    Tickets which are deprecating something or removing something which was already deprecated.

misc
    Tickets which are very minor and not worth summarizing outside of the svn changelog. These should be empty (their contents will be ignored).


To get a sense of how the text in these files is presented to users, take a look at `an example of a real overall news file`_ and `an example of a subproject news file`_. The goal when writing the content for one of these files is to produce text that will fit well into the overall news files.

The entry should contain a high-level description of the change suitable for end users. Generally, the grammatical subject of the sentence should be a Python object, and the verb should be something that the object does, prefixed with "now".

Here are some examples:

Features:

    twisted.protocols.amp now raises InvalidSignature when bad arguments are passed to Command.makeArguments

    The new module twisted.internet.endpoints provides an interface for specifying address families separately from socket types.


Deprecations:

    twisted.trial.util.findObject is now deprecated.

    twisted.conch.insults.colors is now deprecated in favor of twisted.conch.insults.helper.

    twisted.runner.procmon.ProcessMonitor's active, consistency, and consistencyDelay attributes are now deprecated.

Removals:

    twisted.internet.interfaces.IReactorTime.cancelCallLater, deprecated since Twisted 2.5, has been removed.

    Support for versions of pyOpenSSL older than 0.10 has been removed.

You don't need to worry about newlines in the file; the contents will be rewrapped when added to the NEWS files.

See `enforcenews.py`_ for the svn pre-commit hook which enforces this policy.


Reporting Bugs
~~~~~~~~~~~~~~
Bugs and feature requests should be filed at the project's `Github page`_.


Running Tests
~~~~~~~~~~~~~
``newsbuilder`` unit tests are found in the ``newsbuilder/test/`` directory and are designed to be run using `trial`_.
`trial`_ will discover the tests automatically, so all you have to do is:

.. code-block:: console

    $ trial newsbuilder
    ...
    Ran 25 tests in 4.338s

    PASSED (successes=25)

This runs the tests with the default Python interpreter.

You can also verify that the tests pass on other supported Python interpreters.
For this we use `tox`_, which will automatically create a `virtualenv`_ for each supported Python version and run the tests.
For example:

.. code-block:: console
    $ pip install --user tox
    $ tox

You may not have all the required Python versions installed,
in which case you will see one or more ``InterpreterNotFound`` errors.

You can also install `tox`_ in a `virtualenv`_ if you prefer not to install it permanently.

.. _Github page: https://github.com/twisted/newsbuilder
.. _an example of a real overall news file: https://twistedmatrix.com/trac/browser/trunk/NEWS
.. _an example of a subproject news file: https://twistedmatrix.com/trac/browser/trunk/twisted/web/topfiles/NEWS
.. _enforcenews.py: http://bazaar.launchpad.net/~exarkun/twisted-trac-integration/trunk/annotate/head%3A/svn-hooks/enforcenews.py
.. _The original documentation for Twisted's newsbuilder: https://twistedmatrix.com/trac/wiki/ReviewProcess#Newsfiles
.. _trial: https://twistedmatrix.com/documents/current/core/howto/trial.html
.. _`tox`: https://pypi.python.org/pypi/tox
.. _`virtualenv`: https://pypi.python.org/pypi/virtualenv
