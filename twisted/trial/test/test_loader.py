import sys, os
from twisted.python import util
from twisted.trial.test import packages
from twisted.trial import unittest
from twisted.trial import runner


class FinderTest(unittest.TestCase):
    def setUp(self):
        packages.setUp()
        self.loader = runner.TestLoader()

    def tearDown(self):
        if sys.modules.has_key('sample'):
            del sys.modules['sample']
        packages.tearDown()

    def test_findPackage(self):
        sample1 = self.loader.findByName('twisted')
        import twisted as sample2
        self.failUnlessEqual(sample1, sample2)
    
    def test_findModule(self):
        sample1 = self.loader.findByName('twisted.trial.test.sample')
        import sample as sample2
        self.failUnlessEqual(sample1, sample2)

    def test_findFile(self):
        path = util.sibpath(__file__, 'sample.py')
        sample1 = self.loader.findByName(path)
        import sample as sample2
        self.failUnlessEqual(sample1, sample2)

    def test_findObject(self):
        sample1 = self.loader.findByName('twisted.trial.test.sample.FooTest')
        import sample
        self.failUnlessEqual(sample.FooTest, sample1)

    def test_findNonModule(self):
        self.failUnlessRaises(AttributeError,
                              self.loader.findByName,
                              'twisted.trial.test.nonexistent')

    def test_findNonPackage(self):
        self.failUnlessRaises(ValueError,
                              self.loader.findByName,
                              'nonextant')

    def test_findNonFile(self):
        path = util.sibpath(__file__, 'nonexistent.py')
        self.failUnlessRaises(ValueError, self.loader.findByName, path)
        
        
class FileTest(unittest.TestCase):
    parent = '_test_loader_FileTest'
    
    def setUp(self):
        self.oldPath = sys.path[:]
        sys.path.append(self.parent)
        packages.setUp(self.parent)

    def tearDown(self):
        importedModules = ['goodpackage',
                           'goodpackage.test_sample',
                           'test_sample',
                           'sample']
        for moduleName in importedModules:
            if sys.modules.has_key(moduleName):
                del sys.modules[moduleName]
        packages.tearDown(self.parent)
        sys.path = self.oldPath

    def test_notFile(self):
        self.failUnlessRaises(ValueError,
                              runner.filenameToModule, 'doesntexist')

    def test_moduleInPath(self):
        sample1 = runner.filenameToModule(util.sibpath(__file__, 'sample.py'))
        import sample as sample2
        self.failUnlessEqual(sample2, sample1)

    def test_moduleNotInPath(self):
        sys.path, newPath = self.oldPath, sys.path
        sample1 = runner.filenameToModule(os.path.join(self.parent,
                                                       'goodpackage',
                                                       'test_sample.py'))
        sys.path = newPath
        from goodpackage import test_sample as sample2
        self.failUnlessEqual(os.path.splitext(sample2.__file__)[0],
                             os.path.splitext(sample1.__file__)[0])

    def test_packageInPath(self):
        package1 = runner.filenameToModule(os.path.join(self.parent,
                                                        'goodpackage'))
        import goodpackage
        self.failUnlessEqual(goodpackage, package1)

    def test_packageNotInPath(self):
        sys.path, newPath = self.oldPath, sys.path
        package1 = runner.filenameToModule(os.path.join(self.parent,
                                                        'goodpackage'))
        sys.path = newPath
        import goodpackage
        self.failUnlessEqual(os.path.splitext(goodpackage.__file__)[0],
                             os.path.splitext(package1.__file__)[0])

    def test_directoryNotPackage(self):
        self.failUnlessRaises(ValueError, runner.filenameToModule,
                              util.sibpath(__file__, 'directory'))

    def test_filenameNotPython(self):
        self.failUnlessRaises(ValueError, runner.filenameToModule,
                              util.sibpath(__file__, 'notpython.py'))

    def test_filenameMatchesPackage(self):
        filename = os.path.join(self.parent, 'goodpackage.py') 
        fd = open(filename, 'w')
        fd.write(packages.testModule)
        fd.close()
        try:
            module = runner.filenameToModule(filename)
            self.failUnlessEqual(filename, module.__file__)
        finally:
            os.remove(filename)


class LoaderTest(unittest.TestCase):

    ## FIXME -- Need tests for:
    ## * loading packages that contain modules with errors
    ## * loading package recursively for packages that contain modules with
    ##   errors
    ## * loading with custom sorter
    ## * the default sort order (alphabetic)
    ## * loading doctests

    ## FIXME -- Need tests (and implementations) for:
    ## * Loading from a string
    ##   * could be a file / directory
    ##   * could be name of a python object

    parent = '_test_loader'
    
    def setUp(self):
        self.loader = runner.TestLoader()
        self.oldPath = sys.path[:]
        sys.path.append(self.parent)
        packages.setUp(self.parent)

    def tearDown(self):
        importedModules = ['goodpackage',
                           'package', 'package.test_bad_module',
                           'package.test_import_module' 'test_sample', 'sample']
        for moduleName in importedModules:
            if sys.modules.has_key(moduleName):
                del sys.modules[moduleName]        
        sys.path = self.oldPath
        packages.tearDown(self.parent)

    def test_loadMethod(self):
        import sample
        suite = self.loader.loadMethod(sample.FooTest.test_foo)
        self.failUnlessEqual(1, suite.countTestCases())
        self.failUnlessEqual(['test_foo'],
                             [test._testMethodName for test in suite._tests])

    def test_loadNonMethod(self):
        import sample
        self.failUnlessRaises(TypeError, self.loader.loadMethod, sample)
        self.failUnlessRaises(TypeError,
                              self.loader.loadMethod, sample.FooTest)
        self.failUnlessRaises(TypeError, self.loader.loadMethod, "string")
        self.failUnlessRaises(TypeError,
                              self.loader.loadMethod, ('foo', 'bar'))

    def test_loadClass(self):
        import sample
        suite = self.loader.loadClass(sample.FooTest)
        self.failUnlessEqual(2, suite.countTestCases())
        self.failUnlessEqual(['test_bar', 'test_foo'],
                             [test._testMethodName for test in suite._tests])

    def test_loadNonClass(self):
        import sample
        self.failUnlessRaises(TypeError, self.loader.loadClass, sample)
        self.failUnlessRaises(TypeError,
                              self.loader.loadClass, sample.FooTest.test_foo)
        self.failUnlessRaises(TypeError, self.loader.loadClass, "string")
        self.failUnlessRaises(TypeError,
                              self.loader.loadClass, ('foo', 'bar'))

    def test_loadNonTestCase(self):
        import sample
        self.failUnlessRaises(ValueError, self.loader.loadClass,
                              sample.NotATest)
        
    def test_loadModule(self):
        import sample
        suite = self.loader.loadModule(sample)
        self.failUnlessEqual(7, suite.countTestCases())
        self.failUnless(isinstance(suite, runner.NamedSuite),
                        "%r must be a runner.NamedSuite instance"
                        % (suite,))

    def test_loadNonModule(self):
        import sample
        self.failUnlessRaises(TypeError,
                              self.loader.loadModule, sample.FooTest)
        self.failUnlessRaises(TypeError,
                              self.loader.loadModule, sample.FooTest.test_foo)
        self.failUnlessRaises(TypeError, self.loader.loadModule, "string")
        self.failUnlessRaises(TypeError,
                              self.loader.loadModule, ('foo', 'bar'))

    def test_loadPackage(self):
        import goodpackage
        suite = self.loader.loadPackage(goodpackage)
        self.failUnlessEqual(7, suite.countTestCases())

    def test_loadPackageWithBadModules(self):
        import package
        suite = self.loader.loadPackage(package, recurse=True)
        importErrors = list(zip(*self.loader.getImportErrors())[0])
        importErrors.sort()
        self.failUnlessEqual(importErrors,
                             ['test_bad_module.py', 'test_import_module.py'])

    def test_loadNonPackage(self):
        import sample
        self.failUnlessRaises(TypeError,
                              self.loader.loadPackage, sample.FooTest)
        self.failUnlessRaises(TypeError,
                              self.loader.loadPackage, sample.FooTest.test_foo)
        self.failUnlessRaises(TypeError, self.loader.loadPackage, "string")
        self.failUnlessRaises(TypeError,
                              self.loader.loadPackage, ('foo', 'bar'))

    def test_loadModuleAsPackage(self):
        import sample
        ## XXX -- should this instead raise a ValueError? -- jml
        self.failUnlessRaises(TypeError, self.loader.loadPackage, sample)
        
    def test_loadPackageRecursive(self):
        import goodpackage
        suite = self.loader.loadPackage(goodpackage, recurse=True)
        self.failUnlessEqual(14, suite.countTestCases())

    def test_loadAnythingOnModule(self):
        import sample
        suite = self.loader.loadAnything(sample)
        self.failUnlessEqual(suite.name(), sample.__name__)

    def test_loadAnythingOnClass(self):
        import sample
        suite = self.loader.loadAnything(sample.FooTest)
        self.failUnless(hasattr(suite, 'name'),
                        '%r is not a named suite' % (suite,))
        self.failUnlessEqual(suite.original, sample.FooTest)
        self.failUnlessEqual(2, suite.countTestCases())
        
    def test_loadAnythingOnMethod(self):
        import sample
        suite = self.loader.loadAnything(sample.FooTest.test_foo)
        self.failUnless(hasattr(suite, 'name'),
                        '%r is not a named suite' % (suite,))
        self.failUnlessEqual(1, suite.countTestCases())

    def test_loadAnythingOnPackage(self):
        import goodpackage
        suite = self.loader.loadAnything(goodpackage)
        self.failUnless(isinstance(suite, self.loader.suiteFactory))
        self.failUnlessEqual(7, suite.countTestCases())
        
    def test_loadAnythingOnPackageRecursive(self):
        import goodpackage
        suite = self.loader.loadAnything(goodpackage, recurse=True)
        self.failUnless(isinstance(suite, self.loader.suiteFactory))
        self.failUnlessEqual(14, suite.countTestCases())
        
    def test_loadAnythingOnString(self):
        # the important thing about this test is not the string-iness
        # but the non-handledness.
        self.failUnlessRaises(TypeError,
                              self.loader.loadAnything, "goodpackage")
