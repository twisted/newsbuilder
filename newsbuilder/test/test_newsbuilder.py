# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{newsbuilder}.

All of these tests are skipped on platforms other than Linux, as the release is
only ever performed on Linux.
"""


import glob
import operator
import os
from StringIO import StringIO
import tarfile
from datetime import date

from twisted.trial.unittest import TestCase

from twisted.python.procutils import which
from twisted.python import release
from twisted.python.filepath import FilePath
from twisted.python.versions import Version

from newsbuilder import (
    findTwistedProjects, replaceInFile,
    replaceProjectVersion, Project, generateVersionFileData,
    runCommand, NewsBuilder, NotWorkingDirectory, TwistedBuildStrategy)

if os.name != 'posix':
    skip = "Release toolchain only supported on POSIX."
else:
    skip = None

if which("svn") and which("svnadmin"):
    svnSkip = skip
else:
    svnSkip = "svn or svnadmin is not present."



def genVersion(*args, **kwargs):
    """
    A convenience for generating _version.py data.

    @param args: Arguments to pass to L{Version}.
    @param kwargs: Keyword arguments to pass to L{Version}.
    """
    return generateVersionFileData(Version(*args, **kwargs))



def createStructure(root, dirDict):
    """
    Create a set of directories and files given a dict defining their
    structure.

    @param root: The directory in which to create the structure.  It must
        already exist.
    @type root: L{FilePath}

    @param dirDict: The dict defining the structure. Keys should be strings
        naming files, values should be strings describing file contents OR
        dicts describing subdirectories.  All files are written in binary
        mode.  Any string values are assumed to describe text files and
        will have their newlines replaced with the platform-native newline
        convention.  For example::

            {"foofile": "foocontents",
             "bardir": {"barfile": "bar\ncontents"}}
    @type dirDict: C{dict}
    """
    for x in dirDict:
        child = root.child(x)
        if isinstance(dirDict[x], dict):
            child.createDirectory()
            createStructure(child, dirDict[x])
        else:
            child.setContent(dirDict[x].replace('\n', os.linesep))



class StructureAssertingMixin(object):
    """
    A mixin for L{TestCase} subclasses which provides some methods for
    asserting the structure and contents of directories and files on the
    filesystem.
    """
    def assertStructure(self, root, dirDict):
        """
        Assert that a directory is equivalent to one described by a dict.

        @param root: The filesystem directory to compare.
        @type root: L{FilePath}
        @param dirDict: The dict that should describe the contents of the
            directory. It should be the same structure as the C{dirDict}
            parameter to L{createStructure}.
        @type dirDict: C{dict}
        """
        children = [each.basename() for each in root.children()]
        for pathSegment, expectation in dirDict.items():
            child = root.child(pathSegment)
            if callable(expectation):
                self.assertTrue(expectation(child))
            elif isinstance(expectation, dict):
                self.assertTrue(child.isdir(), "%s is not a dir!"
                                % (child.path,))
                self.assertStructure(child, expectation)
            else:
                actual = child.getContent().replace(os.linesep, '\n')
                self.assertEqual(actual, expectation)
            children.remove(pathSegment)
        if children:
            self.fail("There were extra children in %s: %s"
                      % (root.path, children))


    def assertExtractedStructure(self, outputFile, dirDict):
        """
        Assert that a tarfile content is equivalent to one described by a dict.

        @param outputFile: The tar file built by L{DistributionBuilder}.
        @type outputFile: L{FilePath}.
        @param dirDict: The dict that should describe the contents of the
            directory. It should be the same structure as the C{dirDict}
            parameter to L{createStructure}.
        @type dirDict: C{dict}
        """
        tarFile = tarfile.TarFile.open(outputFile.path, "r:bz2")
        extracted = FilePath(self.mktemp())
        extracted.createDirectory()
        for info in tarFile:
            tarFile.extract(info, path=extracted.path)
        self.assertStructure(extracted.children()[0], dirDict)



class ProjectTest(TestCase):
    """
    There is a first-class representation of a project.
    """

    def assertProjectsEqual(self, observedProjects, expectedProjects):
        """
        Assert that two lists of L{Project}s are equal.
        """
        self.assertEqual(len(observedProjects), len(expectedProjects))
        observedProjects = sorted(observedProjects,
                                  key=operator.attrgetter('directory'))
        expectedProjects = sorted(expectedProjects,
                                  key=operator.attrgetter('directory'))
        for observed, expected in zip(observedProjects, expectedProjects):
            self.assertEqual(observed.directory, expected.directory)


    def makeProject(self, version, baseDirectory=None):
        """
        Make a Twisted-style project in the given base directory.

        @param baseDirectory: The directory to create files in
            (as a L{FilePath).
        @param version: The version information for the project.
        @return: L{Project} pointing to the created project.
        """
        if baseDirectory is None:
            baseDirectory = FilePath(self.mktemp())
            baseDirectory.createDirectory()
        segments = version.package.split('.')
        directory = baseDirectory
        for segment in segments:
            directory = directory.child(segment)
            if not directory.exists():
                directory.createDirectory()
            directory.child('__init__.py').setContent('')
        directory.child('topfiles').createDirectory()
        directory.child('topfiles').child('README').setContent(version.base())
        replaceProjectVersion(
            directory.child('_version.py').path, version)
        return Project(directory)


    def makeProjects(self, *versions):
        """
        Create a series of projects underneath a temporary base directory.

        @return: A L{FilePath} for the base directory.
        """
        baseDirectory = FilePath(self.mktemp())
        baseDirectory.createDirectory()
        for version in versions:
            self.makeProject(version, baseDirectory)
        return baseDirectory


    def test_getVersion(self):
        """
        Project objects know their version.
        """
        version = Version('foo', 2, 1, 0)
        project = self.makeProject(version)
        self.assertEqual(project.getVersion(), version)


    def test_updateVersion(self):
        """
        Project objects know how to update the version numbers in those
        projects.
        """
        project = self.makeProject(Version("bar", 2, 1, 0))
        newVersion = Version("bar", 3, 2, 9)
        project.updateVersion(newVersion)
        self.assertEqual(project.getVersion(), newVersion)
        self.assertEqual(
            project.directory.child("topfiles").child("README").getContent(),
            "3.2.9")


    def test_repr(self):
        """
        The representation of a Project is Project(directory).
        """
        foo = Project(FilePath('bar'))
        self.assertEqual(
            repr(foo), 'Project(%r)' % (foo.directory))


    def test_findTwistedStyleProjects(self):
        """
        findTwistedStyleProjects finds all projects underneath a particular
        directory. A 'project' is defined by the existence of a 'topfiles'
        directory and is returned as a Project object.
        """
        baseDirectory = self.makeProjects(
            Version('foo', 2, 3, 0), Version('foo.bar', 0, 7, 4))
        projects = findTwistedProjects(baseDirectory)
        self.assertProjectsEqual(
            projects,
            [Project(baseDirectory.child('foo')),
             Project(baseDirectory.child('foo').child('bar'))])



class UtilityTest(TestCase):
    """
    Tests for various utility functions for releasing.
    """

    def test_chdir(self):
        """
        Test that the runChdirSafe is actually safe, i.e., it still
        changes back to the original directory even if an error is
        raised.
        """
        cwd = os.getcwd()

        def chAndBreak():
            os.mkdir('releaseCh')
            os.chdir('releaseCh')
            1 // 0

        self.assertRaises(ZeroDivisionError,
                          release.runChdirSafe, chAndBreak)
        self.assertEqual(cwd, os.getcwd())



    def test_replaceInFile(self):
        """
        L{replaceInFile} replaces data in a file based on a dict. A key from
        the dict that is found in the file is replaced with the corresponding
        value.
        """
        content = 'foo\nhey hey $VER\nbar\n'
        outf = open('release.replace', 'w')
        outf.write(content)
        outf.close()

        expected = content.replace('$VER', '2.0.0')
        replaceInFile('release.replace', {'$VER': '2.0.0'})
        self.assertEqual(open('release.replace').read(), expected)


        expected = expected.replace('2.0.0', '3.0.0')
        replaceInFile('release.replace', {'2.0.0': '3.0.0'})
        self.assertEqual(open('release.replace').read(), expected)



def svnCommit(project, repository):
    """
    Make the C{project} directory a valid subversion directory with all
    files committed to C{repository}.
    """
    runCommand(["svnadmin", "create", repository.path])
    runCommand(["svn", "checkout", "file://" + repository.path,
                project.path])

    runCommand(["svn", "add"] + glob.glob(project.path + "/*"))
    runCommand(["svn", "commit", project.path, "-m", "yay"])



def createFakeTwistedProject(project):
    """
    Create a fake-looking Twisted project to build from.
    """
    project = project.child("twisted")
    project.makedirs()
    createStructure(
        project, {
            'NEWS': 'Old boring stuff from the past.\n',
            '_version.py': genVersion("twisted", 1, 2, 3),
            'topfiles': {
                'NEWS': 'Old core news.\n',
                '3.feature': 'Third feature addition.\n',
                '5.misc': ''},
            'conch': {
                '_version.py': genVersion("twisted.conch", 3, 4, 5),
                'topfiles': {
                    'NEWS': 'Old conch news.\n',
                    '7.bugfix': 'Fixed that bug.\n'}}})
    return project



class NewsBuilderTests(TestCase, StructureAssertingMixin):
    """
    Tests for L{NewsBuilder}.
    """
    skip = svnSkip

    def setUp(self):
        """
        Create a fake project and stuff some basic structure and content into
        it.
        """
        self.builder = NewsBuilder()
        self.project = FilePath(self.mktemp())
        self.project.createDirectory()

        self.existingText = 'Here is stuff which was present previously.\n'
        createStructure(
            self.project, {
                'NEWS': self.existingText,
                '5.feature': 'We now support the web.\n',
                '12.feature': 'The widget is more robust.\n',
                '15.feature': (
                    'A very long feature which takes many words to '
                    'describe with any accuracy was introduced so that '
                    'the line wrapping behavior of the news generating '
                    'code could be verified.\n'),
                '16.feature': (
                    'A simpler feature\ndescribed on multiple lines\n'
                    'was added.\n'),
                '23.bugfix': 'Broken stuff was fixed.\n',
                '25.removal': 'Stupid stuff was deprecated.\n',
                '30.misc': '',
                '35.misc': '',
                '40.doc': 'foo.bar.Baz.quux',
                '41.doc': 'writing Foo servers'})


    def test_today(self):
        """
        L{NewsBuilder._today} returns today's date in YYYY-MM-DD form.
        """
        self.assertEqual(
            self.builder._today(), date.today().strftime('%Y-%m-%d'))


    def test_findFeatures(self):
        """
        When called with L{NewsBuilder._FEATURE}, L{NewsBuilder._findChanges}
        returns a list of bugfix ticket numbers and descriptions as a list of
        two-tuples.
        """
        features = self.builder._findChanges(
            self.project, self.builder._FEATURE)
        self.assertEqual(
            features,
            [(5, "We now support the web."),
             (12, "The widget is more robust."),
             (15,
              "A very long feature which takes many words to describe with "
              "any accuracy was introduced so that the line wrapping behavior "
              "of the news generating code could be verified."),
             (16, "A simpler feature described on multiple lines was added.")])


    def test_findBugfixes(self):
        """
        When called with L{NewsBuilder._BUGFIX}, L{NewsBuilder._findChanges}
        returns a list of bugfix ticket numbers and descriptions as a list of
        two-tuples.
        """
        bugfixes = self.builder._findChanges(
            self.project, self.builder._BUGFIX)
        self.assertEqual(
            bugfixes,
            [(23, 'Broken stuff was fixed.')])


    def test_findRemovals(self):
        """
        When called with L{NewsBuilder._REMOVAL}, L{NewsBuilder._findChanges}
        returns a list of removal/deprecation ticket numbers and descriptions
        as a list of two-tuples.
        """
        removals = self.builder._findChanges(
            self.project, self.builder._REMOVAL)
        self.assertEqual(
            removals,
            [(25, 'Stupid stuff was deprecated.')])


    def test_findDocumentation(self):
        """
        When called with L{NewsBuilder._DOC}, L{NewsBuilder._findChanges}
        returns a list of documentation ticket numbers and descriptions as a
        list of two-tuples.
        """
        doc = self.builder._findChanges(
            self.project, self.builder._DOC)
        self.assertEqual(
            doc,
            [(40, 'foo.bar.Baz.quux'),
             (41, 'writing Foo servers')])


    def test_findMiscellaneous(self):
        """
        When called with L{NewsBuilder._MISC}, L{NewsBuilder._findChanges}
        returns a list of removal/deprecation ticket numbers and descriptions
        as a list of two-tuples.
        """
        misc = self.builder._findChanges(
            self.project, self.builder._MISC)
        self.assertEqual(
            misc,
            [(30, ''),
             (35, '')])


    def test_writeHeader(self):
        """
        L{NewsBuilder._writeHeader} accepts a file-like object opened for
        writing and a header string and writes out a news file header to it.
        """
        output = StringIO()
        self.builder._writeHeader(output, "Super Awesometastic 32.16")
        self.assertEqual(
            output.getvalue(),
            "Super Awesometastic 32.16\n"
            "=========================\n"
            "\n")


    def test_writeSection(self):
        """
        L{NewsBuilder._writeSection} accepts a file-like object opened for
        writing, a section name, and a list of ticket information (as returned
        by L{NewsBuilder._findChanges}) and writes out a section header and all
        of the given ticket information.
        """
        output = StringIO()
        self.builder._writeSection(
            output, "Features",
            [(3, "Great stuff."),
             (17, "Very long line which goes on and on and on, seemingly "
              "without end until suddenly without warning it does end.")])
        self.assertEqual(
            output.getvalue(),
            "Features\n"
            "--------\n"
            " - Great stuff. (#3)\n"
            " - Very long line which goes on and on and on, seemingly "
            "without end\n"
            "   until suddenly without warning it does end. (#17)\n"
            "\n")


    def test_writeMisc(self):
        """
        L{NewsBuilder._writeMisc} accepts a file-like object opened for
        writing, a section name, and a list of ticket information (as returned
        by L{NewsBuilder._findChanges} and writes out a section header and all
        of the ticket numbers, but excludes any descriptions.
        """
        output = StringIO()
        self.builder._writeMisc(
            output, "Other",
            [(x, "") for x in range(2, 50, 3)])
        self.assertEqual(
            output.getvalue(),
            "Other\n"
            "-----\n"
            " - #2, #5, #8, #11, #14, #17, #20, #23, #26, #29, #32, #35, "
            "#38, #41,\n"
            "   #44, #47\n"
            "\n")


    def test_build(self):
        """
        L{NewsBuilder.build} updates a NEWS file with new features based on the
        I{<ticket>.feature} files found in the directory specified.
        """
        self.builder.build(
            self.project, self.project.child('NEWS'),
            "Super Awesometastic 32.16")

        results = self.project.child('NEWS').getContent()
        self.assertEqual(
            results,
            'Super Awesometastic 32.16\n'
            '=========================\n'
            '\n'
            'Features\n'
            '--------\n'
            ' - We now support the web. (#5)\n'
            ' - The widget is more robust. (#12)\n'
            ' - A very long feature which takes many words to describe '
            'with any\n'
            '   accuracy was introduced so that the line wrapping behavior '
            'of the\n'
            '   news generating code could be verified. (#15)\n'
            ' - A simpler feature described on multiple lines was '
            'added. (#16)\n'
            '\n'
            'Bugfixes\n'
            '--------\n'
            ' - Broken stuff was fixed. (#23)\n'
            '\n'
            'Improved Documentation\n'
            '----------------------\n'
            ' - foo.bar.Baz.quux (#40)\n'
            ' - writing Foo servers (#41)\n'
            '\n'
            'Deprecations and Removals\n'
            '-------------------------\n'
            ' - Stupid stuff was deprecated. (#25)\n'
            '\n'
            'Other\n'
            '-----\n'
            ' - #30, #35\n'
            '\n\n' + self.existingText)


    def test_emptyProjectCalledOut(self):
        """
        If no changes exist for a project, I{NEWS} gains a new section for
        that project that includes some helpful text about how there were no
        interesting changes.
        """
        project = FilePath(self.mktemp()).child("twisted")
        project.makedirs()
        createStructure(project, {'NEWS': self.existingText})

        self.builder.build(
            project, project.child('NEWS'),
            "Super Awesometastic 32.16")
        results = project.child('NEWS').getContent()
        self.assertEqual(
            results,
            'Super Awesometastic 32.16\n'
            '=========================\n'
            '\n' +
            self.builder._NO_CHANGES +
            '\n\n' + self.existingText)


    def test_preserveTicketHint(self):
        """
        If a I{NEWS} file begins with the two magic lines which point readers
        at the issue tracker, those lines are kept at the top of the new file.
        """
        news = self.project.child('NEWS')
        news.setContent(
            'Ticket numbers in this file can be looked up by visiting\n'
            'http://twistedmatrix.com/trac/ticket/<number>\n'
            '\n'
            'Blah blah other stuff.\n')

        self.builder.build(self.project, news, "Super Awesometastic 32.16")

        self.assertEqual(
            news.getContent(),
            'Ticket numbers in this file can be looked up by visiting\n'
            'http://twistedmatrix.com/trac/ticket/<number>\n'
            '\n'
            'Super Awesometastic 32.16\n'
            '=========================\n'
            '\n'
            'Features\n'
            '--------\n'
            ' - We now support the web. (#5)\n'
            ' - The widget is more robust. (#12)\n'
            ' - A very long feature which takes many words to describe '
            'with any\n'
            '   accuracy was introduced so that the line wrapping behavior '
            'of the\n'
            '   news generating code could be verified. (#15)\n'
            ' - A simpler feature described on multiple lines was '
            'added. (#16)\n'
            '\n'
            'Bugfixes\n'
            '--------\n'
            ' - Broken stuff was fixed. (#23)\n'
            '\n'
            'Improved Documentation\n'
            '----------------------\n'
            ' - foo.bar.Baz.quux (#40)\n'
            ' - writing Foo servers (#41)\n'
            '\n'
            'Deprecations and Removals\n'
            '-------------------------\n'
            ' - Stupid stuff was deprecated. (#25)\n'
            '\n'
            'Other\n'
            '-----\n'
            ' - #30, #35\n'
            '\n\n'
            'Blah blah other stuff.\n')


    def test_emptySectionsOmitted(self):
        """
        If there are no changes of a particular type (feature, bugfix, etc), no
        section for that type is written by L{NewsBuilder.build}.
        """
        for ticket in self.project.children():
            if ticket.splitext()[1] in ('.feature', '.misc', '.doc'):
                ticket.remove()

        self.builder.build(
            self.project, self.project.child('NEWS'),
            'Some Thing 1.2')

        self.assertEqual(
            self.project.child('NEWS').getContent(),
            'Some Thing 1.2\n'
            '==============\n'
            '\n'
            'Bugfixes\n'
            '--------\n'
            ' - Broken stuff was fixed. (#23)\n'
            '\n'
            'Deprecations and Removals\n'
            '-------------------------\n'
            ' - Stupid stuff was deprecated. (#25)\n'
            '\n\n'
            'Here is stuff which was present previously.\n')


    def test_duplicatesMerged(self):
        """
        If two change files have the same contents, they are merged in the
        generated news entry.
        """
        def feature(s):
            return self.project.child(s + '.feature')
        feature('5').copyTo(feature('15'))
        feature('5').copyTo(feature('16'))

        self.builder.build(
            self.project, self.project.child('NEWS'),
            'Project Name 5.0')

        self.assertEqual(
            self.project.child('NEWS').getContent(),
            'Project Name 5.0\n'
            '================\n'
            '\n'
            'Features\n'
            '--------\n'
            ' - We now support the web. (#5, #15, #16)\n'
            ' - The widget is more robust. (#12)\n'
            '\n'
            'Bugfixes\n'
            '--------\n'
            ' - Broken stuff was fixed. (#23)\n'
            '\n'
            'Improved Documentation\n'
            '----------------------\n'
            ' - foo.bar.Baz.quux (#40)\n'
            ' - writing Foo servers (#41)\n'
            '\n'
            'Deprecations and Removals\n'
            '-------------------------\n'
            ' - Stupid stuff was deprecated. (#25)\n'
            '\n'
            'Other\n'
            '-----\n'
            ' - #30, #35\n'
            '\n\n'
            'Here is stuff which was present previously.\n')


    def test_buildAll(self):
        """
        L{NewsBuilder.buildAll} calls L{NewsBuilder.build} once for each
        subproject, passing that subproject's I{topfiles} directory as C{path},
        the I{NEWS} file in that directory as C{output}, and the subproject's
        name as C{header}, and then again for each subproject with the
        top-level I{NEWS} file for C{output}. Blacklisted subprojects are
        skipped.
        """
        builds = []
        builder = NewsBuilder()
        builder.build = lambda path, output, header: builds.append((
            path, output, header))
        builder._today = lambda: '2009-12-01'

        project = createFakeTwistedProject(FilePath(self.mktemp()))
        svnCommit(project, repository=FilePath(self.mktemp()))
        builder.buildAll(project)

        coreTopfiles = project.child("topfiles")
        coreNews = coreTopfiles.child("NEWS")
        coreHeader = "Twisted Core 1.2.3 (2009-12-01)"

        conchTopfiles = project.child("conch").child("topfiles")
        conchNews = conchTopfiles.child("NEWS")
        conchHeader = "Twisted Conch 3.4.5 (2009-12-01)"

        aggregateNews = project.child("NEWS")

        self.assertEqual(
            builds,
            [(conchTopfiles, conchNews, conchHeader),
             (conchTopfiles, aggregateNews, conchHeader),
             (coreTopfiles, coreNews, coreHeader),
             (coreTopfiles, aggregateNews, coreHeader)])


    def test_buildAllAggregate(self):
        """
        L{NewsBuilder.buildAll} aggregates I{NEWS} information into the top
        files, only deleting fragments once it's done.
        """
        builder = NewsBuilder()
        project = createFakeTwistedProject(FilePath(self.mktemp()))
        svnCommit(project, repository=FilePath(self.mktemp()))
        builder.buildAll(project)

        aggregateNews = project.child("NEWS")

        aggregateContent = aggregateNews.getContent()
        self.assertIn("Third feature addition", aggregateContent)
        self.assertIn("Fixed that bug", aggregateContent)
        self.assertIn("Old boring stuff from the past", aggregateContent)


    def test_changeVersionInNews(self):
        """
        L{NewsBuilder._changeVersions} gets the release date for a given
        version of a project as a string.
        """
        builder = NewsBuilder()
        builder._today = lambda: '2009-12-01'
        project = createFakeTwistedProject(FilePath(self.mktemp()))
        svnCommit(project, repository=FilePath(self.mktemp()))
        builder.buildAll(project)
        newVersion = Version('TEMPLATE', 7, 7, 14)
        coreNews = project.child('topfiles').child('NEWS')
        # twisted 1.2.3 is the old version.
        builder._changeNewsVersion(
            coreNews, "Core", Version("twisted", 1, 2, 3),
            newVersion, '2010-01-01')
        expectedCore = (
            'Twisted Core 7.7.14 (2010-01-01)\n'
            '================================\n'
            '\n'
            'Features\n'
            '--------\n'
            ' - Third feature addition. (#3)\n'
            '\n'
            'Other\n'
            '-----\n'
            ' - #5\n\n\n')
        self.assertEqual(
            expectedCore + 'Old core news.\n', coreNews.getContent())


    def test_removeNEWSfragments(self):
        """
        L{NewsBuilder.buildALL} removes all the NEWS fragments after the build
        process, using the C{svn} C{rm} command.
        """
        builder = NewsBuilder()
        project = createFakeTwistedProject(FilePath(self.mktemp()))
        svnCommit(project, repository=FilePath(self.mktemp()))
        builder.buildAll(project)

        self.assertEqual(5, len(project.children()))
        output = runCommand(["svn", "status", project.path])
        removed = [line for line in output.splitlines()
                   if line.startswith("D ")]
        self.assertEqual(3, len(removed))


    def test_checkSVN(self):
        """
        L{NewsBuilder.buildAll} raises L{NotWorkingDirectory} when the given
        path is not a SVN checkout.
        """
        self.assertRaises(
            NotWorkingDirectory, self.builder.buildAll, self.project)



class TwistedBuildStrategyTests(TestCase):
    """
    Tests for L{TwistedBuildStrategy}.
    """
    def test_today(self):
        """
        L{TwistedBuildStrategy._today} returns today's date in YYYY-MM-DD form.
        """
        strategy = TwistedBuildStrategy(newsBuilder=object())
        self.assertEqual(
            strategy._today(), date.today().strftime('%Y-%m-%d'))


    def test_buildAll(self):
        """
        L{TwistedBuildStrategy.buildAll} calls L{NewsBuilder.build} once for each
        subproject, passing that subproject's I{topfiles} directory as C{path},
        the I{NEWS} file in that directory as C{output}, and the subproject's
        name as C{header}, and then again for each subproject with the
        top-level I{NEWS} file for C{output}. Blacklisted subprojects are
        skipped.
        """
        builds = []
        builder = NewsBuilder()
        builder.build = lambda path, output, header: builds.append((
            path, output, header))

        project = createFakeTwistedProject(FilePath(self.mktemp()))
        svnCommit(project, repository=FilePath(self.mktemp()))
        strategy = TwistedBuildStrategy(newsBuilder=builder)
        strategy._today = lambda: '2009-12-01'
        strategy.buildAll(project)

        coreTopfiles = project.child("topfiles")
        coreNews = coreTopfiles.child("NEWS")
        coreHeader = "Twisted Core 1.2.3 (2009-12-01)"

        conchTopfiles = project.child("conch").child("topfiles")
        conchNews = conchTopfiles.child("NEWS")
        conchHeader = "Twisted Conch 3.4.5 (2009-12-01)"

        aggregateNews = project.child("NEWS")

        self.assertEqual(
            builds,
            [(conchTopfiles, conchNews, conchHeader),
             (conchTopfiles, aggregateNews, conchHeader),
             (coreTopfiles, coreNews, coreHeader),
             (coreTopfiles, aggregateNews, coreHeader)])


    def test_buildAllAggregate(self):
        """
        L{NewsBuilder.buildAll} aggregates I{NEWS} information into the top
        files, only deleting fragments once it's done.
        """
        builder = NewsBuilder()
        project = createFakeTwistedProject(FilePath(self.mktemp()))
        svnCommit(project, repository=FilePath(self.mktemp()))
        strategy = TwistedBuildStrategy(newsBuilder=builder)
        strategy.buildAll(project)

        aggregateNews = project.child("NEWS")

        aggregateContent = aggregateNews.getContent()
        self.assertIn("Third feature addition", aggregateContent)
        self.assertIn("Fixed that bug", aggregateContent)
        self.assertIn("Old boring stuff from the past", aggregateContent)


    def test_removeNEWSfragments(self):
        """
        L{TwistedBuildStrategy.buildALL} removes all the NEWS fragments after
        the build process, using the C{svn} C{rm} command.
        """
        builder = NewsBuilder()
        project = createFakeTwistedProject(FilePath(self.mktemp()))
        svnCommit(project, repository=FilePath(self.mktemp()))
        strategy = TwistedBuildStrategy(newsBuilder=builder)
        strategy.buildAll(project)

        self.assertEqual(5, len(project.children()))
        output = runCommand(["svn", "status", project.path])
        removed = [line for line in output.splitlines()
                   if line.startswith("D ")]
        self.assertEqual(3, len(removed))


    def test_checkSVN(self):
        """
        L{TwistedBuildStrategy.buildAll} raises L{NotWorkingDirectory} when the
        given path is not a SVN checkout.
        """
        strategy = TwistedBuildStrategy(newsBuilder=object())
        self.assertRaises(
            NotWorkingDirectory,
            strategy.buildAll,
            createFakeTwistedProject(FilePath(self.mktemp()))
        )
