# -*- test-case-name: twisted.python.test.test_release -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Twisted's automated release system.

This module is only for use within Twisted's release system. If you are anyone
else, do not use it. The interface and behaviour will change without notice.

Only Linux is supported by this code.  It should not be used by any tools
which must run on multiple platforms (eg the setup.py script).
"""

import textwrap
from datetime import date
import re
import sys
import os

from subprocess import PIPE, STDOUT, Popen

from twisted.python.filepath import FilePath
from twisted.python.compat import execfile
from twisted.python import usage

# The offset between a year and the corresponding major version number.
VERSION_OFFSET = 2000


def runCommand(args):
    """
    Execute a vector of arguments.

    @type args: C{list} of C{str}
    @param args: A list of arguments, the first of which will be used as the
        executable to run.

    @rtype: C{str}
    @return: All of the standard output.

    @raise CommandFailed: when the program exited with a non-0 exit code.
    """
    process = Popen(args, stdout=PIPE, stderr=STDOUT)
    stdout = process.stdout.read()
    exitCode = process.wait()
    if exitCode < 0:
        raise CommandFailed(None, -exitCode, stdout)
    elif exitCode > 0:
        raise CommandFailed(exitCode, None, stdout)
    return stdout



class CommandFailed(Exception):
    """
    Raised when a child process exits unsuccessfully.

    @type exitStatus: C{int}
    @ivar exitStatus: The exit status for the child process.

    @type exitSignal: C{int}
    @ivar exitSignal: The exit signal for the child process.

    @type output: C{str}
    @ivar output: The bytes read from stdout and stderr of the child process.
    """
    def __init__(self, exitStatus, exitSignal, output):
        Exception.__init__(self, exitStatus, exitSignal, output)
        self.exitStatus = exitStatus
        self.exitSignal = exitSignal
        self.output = output



def _changeVersionInFile(old, new, filename):
    """
    Replace the C{old} version number with the C{new} one in the given
    C{filename}.
    """
    replaceInFile(filename, {old.base(): new.base()})



class Project(object):
    """
    A representation of a project that has a version.

    @ivar directory: A L{twisted.python.filepath.FilePath} pointing to the base
        directory of a Twisted-style Python package. The package should contain
        a C{_version.py} file and a C{topfiles} directory that contains a
        C{README} file.
    """

    def __init__(self, directory):
        self.directory = directory


    def __repr__(self):
        return '%s(%r)' % (
            self.__class__.__name__, self.directory)


    def getVersion(self):
        """
        @return: A L{Version} specifying the version number of the project
        based on live python modules.
        """
        namespace = {}
        execfile(self.directory.child("_version.py").path, namespace)
        return namespace["get_versions"]()['version']


    def updateVersion(self, version):
        """
        Replace the existing version numbers in _version.py and README files
        with the specified version.
        """
        oldVersion = self.getVersion()
        replaceProjectVersion(self.directory.child("_version.py").path,
                              version)
        _changeVersionInFile(
            oldVersion, version,
            self.directory.child("topfiles").child("README").path)



def findTwistedProjects(baseDirectory):
    """
    Find all Twisted-style projects beneath a base directory.

    @param baseDirectory: A L{twisted.python.filepath.FilePath} to look inside.
    @return: A list of L{Project}.
    """
    projects = []
    for filePath in baseDirectory.walk():
        if filePath.basename() == 'topfiles':
            projectDirectory = filePath.parent()
            projects.append(Project(projectDirectory))
    return projects




def generateVersionFileData(version):
    """
    Generate the data to be placed into a _version.py file.

    @param version: A version object.
    """
    if version.prerelease is not None:
        prerelease = ", prerelease=%r" % (version.prerelease,)
    else:
        prerelease = ""
    data = '''\
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

# This is an auto-generated file. Do not edit it.

"""
Provides Twisted version information.
"""

from twisted.python import versions
version = versions.Version(%r, %s, %s, %s%s)
''' % (version.package, version.major, version.minor, version.micro,
       prerelease)
    return data



def replaceProjectVersion(filename, newversion):
    """
    Write version specification code into the given filename, which
    sets the version to the given version number.

    @param filename: A filename which is most likely a "_version.py"
        under some Twisted project.
    @param newversion: A version object.
    """
    # XXX - this should be moved to Project and renamed to writeVersionFile.
    # jml, 2007-11-15.
    f = open(filename, 'w')
    f.write(generateVersionFileData(newversion))
    f.close()



def replaceInFile(filename, oldToNew):
    """
    I replace the text `oldstr' with `newstr' in `filename' using science.
    """
    os.rename(filename, filename + '.bak')
    f = open(filename + '.bak')
    d = f.read()
    f.close()
    for k, v in oldToNew.items():
        d = d.replace(k, v)
    f = open(filename + '.new', 'w')
    f.write(d)
    f.close()
    os.rename(filename + '.new', filename)
    os.unlink(filename + '.bak')



class NewsBuilder(object):
    """
    Generate the new section of a NEWS file.

    The C{_FEATURE}, C{_BUGFIX}, C{_DOC}, C{_REMOVAL}, and C{_MISC}
    attributes of this class are symbolic names for the news entry types
    which are supported.  Conveniently, they each also take on the value of
    the file name extension which indicates a news entry of that type.

    @cvar _headings: A C{dict} mapping one of the news entry types to the
        heading to write out for that type of news entry.

    @cvar _NO_CHANGES: A C{str} giving the text which appears when there are
        no significant changes in a release.

    @cvar _TICKET_HINT: A C{str} giving the text which appears at the top of
        each news file and which should be kept at the top, not shifted down
        with all the other content.  Put another way, this is the text after
        which the new news text is inserted.
    """

    _FEATURE = ".feature"
    _BUGFIX = ".bugfix"
    _DOC = ".doc"
    _REMOVAL = ".removal"
    _MISC = ".misc"

    _headings = {
        _FEATURE: "Features",
        _BUGFIX: "Bugfixes",
        _DOC: "Improved Documentation",
        _REMOVAL: "Deprecations and Removals",
        _MISC: "Other"}

    _NO_CHANGES = "No significant changes have been made for this release.\n"

    _TICKET_HINT = (
        'Ticket numbers in this file can be looked up by visiting\n'
        'http://twistedmatrix.com/trac/ticket/<number>\n'
        '\n')

    def _today(self):
        """
        Return today's date as a string in YYYY-MM-DD format.
        """
        return date.today().strftime('%Y-%m-%d')


    def _findChanges(self, path, ticketType):
        """
        Load all the feature ticket summaries.

        @param path: A L{FilePath} the direct children of which to search
            for news entries.

        @param ticketType: The type of news entries to search for.  One of
            L{NewsBuilder._FEATURE}, L{NewsBuilder._BUGFIX},
            L{NewsBuilder._REMOVAL}, or L{NewsBuilder._MISC}.

        @return: A C{list} of two-tuples.  The first element is the ticket
            number as an C{int}.  The second element of each tuple is the
            description of the feature.
        """
        results = []
        for child in path.children():
            base, ext = os.path.splitext(child.basename())
            if ext == ticketType:
                results.append((
                    int(base),
                    ' '.join(child.getContent().splitlines())))
        results.sort()
        return results


    def _formatHeader(self, header):
        """
        Format a header for a NEWS file.

        A header is a title with '=' signs underlining it.

        @param header: The header string to format.
        @type header: C{str}
        @return: A C{str} containing C{header}.
        """
        return header + '\n' + '=' * len(header) + '\n\n'


    def _writeHeader(self, fileObj, header):
        """
        Write a version header to the given file.

        @param fileObj: A file-like object to which to write the header.
        @param header: The header to write to the file.
        @type header: C{str}
        """
        fileObj.write(self._formatHeader(header))


    def _writeSection(self, fileObj, header, tickets):
        """
        Write out one section (features, bug fixes, etc) to the given file.

        @param fileObj: A file-like object to which to write the news section.

        @param header: The header for the section to write.
        @type header: C{str}

        @param tickets: A C{list} of ticket information of the sort returned
            by L{NewsBuilder._findChanges}.
        """
        if not tickets:
            return

        reverse = {}
        for (ticket, description) in tickets:
            reverse.setdefault(description, []).append(ticket)
        for description in reverse:
            reverse[description].sort()
        reverse = reverse.items()
        reverse.sort(key=lambda (descr, tickets): tickets[0])

        fileObj.write(header + '\n' + '-' * len(header) + '\n')
        for (description, relatedTickets) in reverse:
            ticketList = ', '.join([
                '#' + str(ticket) for ticket in relatedTickets])
            entry = ' - %s (%s)' % (description, ticketList)
            entry = textwrap.fill(entry, subsequent_indent='   ')
            fileObj.write(entry + '\n')
        fileObj.write('\n')


    def _writeMisc(self, fileObj, header, tickets):
        """
        Write out a miscellaneous-changes section to the given file.

        @param fileObj: A file-like object to which to write the news section.

        @param header: The header for the section to write.
        @type header: C{str}

        @param tickets: A C{list} of ticket information of the sort returned
            by L{NewsBuilder._findChanges}.
        """
        if not tickets:
            return

        fileObj.write(header + '\n' + '-' * len(header) + '\n')
        formattedTickets = []
        for (ticket, ignored) in tickets:
            formattedTickets.append('#' + str(ticket))
        entry = ' - ' + ', '.join(formattedTickets)
        entry = textwrap.fill(entry, subsequent_indent='   ')
        fileObj.write(entry + '\n\n')


    def build(self, path, output, header):
        """
        Load all of the change information from the given directory and write
        it out to the given output file.

        @param path: A directory (probably a I{topfiles} directory) containing
            change information in the form of <ticket>.<change type> files.
        @type path: L{FilePath}

        @param output: The NEWS file to which the results will be prepended.
        @type output: L{FilePath}

        @param header: The top-level header to use when writing the news.
        @type header: L{str}

        @raise NotWorkingDirectory: If the C{path} is not an SVN checkout.
        """
        changes = []
        for part in (self._FEATURE, self._BUGFIX, self._DOC, self._REMOVAL):
            tickets = self._findChanges(path, part)
            if tickets:
                changes.append((part, tickets))
        misc = self._findChanges(path, self._MISC)

        oldNews = output.getContent()
        newNews = output.sibling('NEWS.new').open('w')
        if oldNews.startswith(self._TICKET_HINT):
            newNews.write(self._TICKET_HINT)
            oldNews = oldNews[len(self._TICKET_HINT):]

        self._writeHeader(newNews, header)
        if changes:
            for (part, tickets) in changes:
                self._writeSection(newNews, self._headings.get(part), tickets)
        else:
            newNews.write(self._NO_CHANGES)
            newNews.write('\n')
        self._writeMisc(newNews, self._headings.get(self._MISC), misc)
        newNews.write('\n')
        newNews.write(oldNews)
        newNews.close()
        output.sibling('NEWS.new').moveTo(output)


    def _deleteFragments(self, path):
        """
        Delete the change information, to clean up the repository  once the
        NEWS files have been built. It requires C{path} to be in a SVN
        directory.

        @param path: A directory (probably a I{topfiles} directory) containing
            change information in the form of <ticket>.<change type> files.
        @type path: L{FilePath}
        """
        ticketTypes = self._headings.keys()
        for child in path.children():
            base, ext = os.path.splitext(child.basename())
            if ext in ticketTypes:
                runCommand(["git", "rm", child.path])


    def _getNewsName(self, project):
        """
        Return the name of C{project} that should appear in NEWS.

        @param project: A L{Project}
        @return: The name of C{project}.
        """
        name = project.directory.basename().title()
        if name == 'Twisted':
            name = 'Core'
        return name


    def _iterProjects(self, baseDirectory):
        """
        Iterate through the Twisted projects in C{baseDirectory}, yielding
        everything we need to know to build news for them.

        Yields C{topfiles}, C{name}, C{version}, for each sub-project in
        reverse-alphabetical order. C{topfile} is the L{FilePath} for the
        topfiles directory, C{name} is the nice name of the project (as should
        appear in the NEWS file), C{version} is the current version string for
        that project.

        @param baseDirectory: A L{FilePath} representing the root directory
            beneath which to find Twisted projects for which to generate
            news (see L{findTwistedProjects}).
        @type baseDirectory: L{FilePath}
        """
        # Get all the subprojects to generate news for
        projects = findTwistedProjects(baseDirectory)
        # And order them alphabetically for ease of reading
        projects.sort(key=lambda proj: proj.directory.path)
        # And generate them backwards since we write news by prepending to
        # files.
        projects.reverse()

        for project in projects:
            topfiles = project.directory.child("topfiles")
            name = self._getNewsName(project)
            version = project.getVersion()
            yield topfiles, name, version


    def buildAll(self, baseDirectory, version):
        """
        Find all of the Twisted subprojects beneath C{baseDirectory} and update
        their news files from the ticket change description files in their
        I{topfiles} directories and update the news file in C{baseDirectory}
        with all of the news.

        @param baseDirectory: A L{FilePath} representing the root directory
            beneath which to find Twisted projects for which to generate
            news (see L{findTwistedProjects}).
        """
        today = self._today()
        header = "Newsbuilder %s (%s)" % (version, today)
        topfiles = baseDirectory.descendant(['newsbuilder', 'topfiles'])
        news = baseDirectory.child("NEWS")
        self.build(topfiles, news, header)
        # Finally, delete the fragments
        self._deleteFragments(topfiles)


    def _changeNewsVersion(self, news, name, oldVersion, newVersion, today):
        """
        Change all references to the current version number in a NEWS file to
        refer to C{newVersion} instead.

        @param news: The NEWS file to change.
        @type news: L{FilePath}
        @param name: The name of the project to change.
        @type name: C{str}
        @param oldVersion: The old version of the project.
        @type oldVersion: L{Version}
        @param newVersion: The new version of the project.
        @type newVersion: L{Version}
        @param today: A YYYY-MM-DD string representing today's date.
        @type today: C{str}
        """
        newHeader = self._formatHeader(
            "Twisted %s %s (%s)" % (name, newVersion.base(), today))
        expectedHeaderRegex = re.compile(
            r"Twisted %s %s \(\d{4}-\d\d-\d\d\)\n=+\n\n" % (
                re.escape(name), re.escape(oldVersion.base())))
        oldNews = news.getContent()
        match = expectedHeaderRegex.search(oldNews)
        if match:
            oldHeader = match.group()
            replaceInFile(news.path, {oldHeader: newHeader})



class NotWorkingDirectory(Exception):
    """
    Raised when a directory does not appear to be an SVN working directory.
    """



class NewsBuilderOptions(usage.Options):
    """
    Command line options for L{NewsBuilderScript}.
    """
    def __init__(self,  stdout=None, stderr=None):
        """
        @param stdout: A file to which stdout messages will be written.
        @param stderr: A file to which stderr messages will be written.
        """
        usage.Options.__init__(self)
        if stdout is None:
            stdout = sys.stdout
        self.stdout = stdout

        if stderr is None:
            stderr = sys.stderr
        self.stderr = stderr


    def opt_version(self):
        """
        Print a version string to I{stdout} and exit with status C{0}.
        """
        from . import __version__
        self.stdout.write(__version__.encode('utf-8') + b'\n')
        raise SystemExit(0)


    def parseArgs(self, repositoryPath, version):
        """
        Handle a repository path supplied as a positional argument and store it
        as a L{FilePath}.
        """
        self['repositoryPath'] = FilePath(repositoryPath)
        self['version'] = version



class NewsBuilderScript(object):
    """
    The entry point for the I{newsbuilder} script.
    """
    def __init__(self, newsBuilder=None, stdout=None, stderr=None):
        """
        @param newsBuilder: A L{NewsBuilder} instance.
        @param stdout: A file to which stdout messages will be written.
        @param stderr: A file to which stderr messages will be written.
        """
        if newsBuilder is None:
            newsBuilder = NewsBuilder()
        self.newsBuilder = newsBuilder

        if stdout is None:
            stdout = sys.stdout
        self.stdout = stdout

        if stderr is None:
            stderr = sys.stderr
        self.stderr = stderr


    def main(self, args):
        """
        The entry point for the I{newsbuilder} script.
        """
        options = NewsBuilderOptions(stdout=self.stdout, stderr=self.stderr)
        try:
            options.parseOptions(args)
        except usage.UsageError as e:
            message = u'ERROR: {}\n'.format(e.message)
            self.stderr.write(message.encode('utf-8'))
            raise SystemExit(1)

        self.newsBuilder.buildAll(options['repositoryPath'], options['version'])
