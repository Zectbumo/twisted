# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.web.util}.
"""


import gc

from twisted.internet import defer
from twisted.python.compat import networkString
from twisted.python.failure import Failure
from twisted.trial.unittest import SynchronousTestCase, TestCase
from twisted.web import resource, util
from twisted.web.error import FlattenerError
from twisted.web.http import FOUND
from twisted.web.server import Request
from twisted.web.template import TagLoader, flattenString, tags
from twisted.web.test.requesthelper import DummyChannel, DummyRequest
from twisted.web.util import (
    DeferredResource,
    FailureElement,
    ParentRedirect,
    _FrameElement,
    _SourceFragmentElement,
    _SourceLineElement,
    _StackElement,
    formatFailure,
    redirectTo,
)


class RedirectToTests(TestCase):
    """
    Tests for L{redirectTo}.
    """

    def test_headersAndCode(self):
        """
        L{redirectTo} will set the C{Location} and C{Content-Type} headers on
        its request, and set the response code to C{FOUND}, so the browser will
        be redirected.
        """
        request = Request(DummyChannel(), True)
        request.method = b"GET"
        targetURL = b"http://target.example.com/4321"
        redirectTo(targetURL, request)
        self.assertEqual(request.code, FOUND)
        self.assertEqual(
            request.responseHeaders.getRawHeaders(b"location"), [targetURL]
        )
        self.assertEqual(
            request.responseHeaders.getRawHeaders(b"content-type"),
            [b"text/html; charset=utf-8"],
        )

    def test_redirectToUnicodeURL(self):
        """
        L{redirectTo} will raise TypeError if unicode object is passed in URL
        """
        request = Request(DummyChannel(), True)
        request.method = b"GET"
        targetURL = "http://target.example.com/4321"
        self.assertRaises(TypeError, redirectTo, targetURL, request)


class ParentRedirectTests(SynchronousTestCase):
    """
    Test L{ParentRedirect}.
    """

    def doLocationTest(self, requestPath: bytes) -> bytes:
        """
        Render a response to a request with path *requestPath*

        @param requestPath: A slash-separated path like C{b'/foo/bar'}.

        @returns: The value of the I{Location} header.
        """
        request = Request(DummyChannel(), True)
        request.method = b"GET"
        request.prepath = requestPath.lstrip(b"/").split(b"/")

        resource = ParentRedirect()
        resource.render(request)

        headers = request.responseHeaders.getRawHeaders(b"Location")
        assert headers is not None
        [location] = headers
        return location

    def test_locationRoot(self):
        """
        At the URL root issue a redirect to the current URL, removing any query
        string.
        """
        self.assertEqual(b"http://10.0.0.1/", self.doLocationTest(b"/"))
        self.assertEqual(b"http://10.0.0.1/", self.doLocationTest(b"/?biff=baff"))

    def test_locationToRoot(self):
        """
        A request for a resource one level down from the URL root produces
        a redirect to the root.
        """
        self.assertEqual(b"http://10.0.0.1/", self.doLocationTest(b"/foo"))
        self.assertEqual(
            b"http://10.0.0.1/", self.doLocationTest(b"/foo?bar=sproiiing")
        )

    def test_locationUpOne(self):
        """
        Requests for resources directly under the path C{/foo/} produce
        redirects to C{/foo/}.
        """
        self.assertEqual(b"http://10.0.0.1/foo/", self.doLocationTest(b"/foo/"))
        self.assertEqual(b"http://10.0.0.1/foo/", self.doLocationTest(b"/foo/bar"))
        self.assertEqual(
            b"http://10.0.0.1/foo/", self.doLocationTest(b"/foo/bar?biz=baz")
        )


class FailureElementTests(TestCase):
    """
    Tests for L{FailureElement} and related helpers which can render a
    L{Failure} as an HTML string.
    """

    def setUp(self):
        """
        Create a L{Failure} which can be used by the rendering tests.
        """

        def lineNumberProbeAlsoBroken():
            message = "This is a problem"
            raise Exception(message)

        # Figure out the line number from which the exception will be raised.
        self.base = lineNumberProbeAlsoBroken.__code__.co_firstlineno + 1

        try:
            lineNumberProbeAlsoBroken()
        except BaseException:
            self.failure = Failure(captureVars=True)
            self.frame = self.failure.frames[-1]

    def test_sourceLineElement(self):
        """
        L{_SourceLineElement} renders a source line and line number.
        """
        element = _SourceLineElement(
            TagLoader(
                tags.div(tags.span(render="lineNumber"), tags.span(render="sourceLine"))
            ),
            50,
            "    print 'hello'",
        )
        d = flattenString(None, element)
        expected = (
            "<div><span>50</span><span>"
            " \N{NO-BREAK SPACE} \N{NO-BREAK SPACE}print 'hello'</span></div>"
        )
        d.addCallback(self.assertEqual, expected.encode("utf-8"))
        return d

    def test_sourceFragmentElement(self):
        """
        L{_SourceFragmentElement} renders source lines at and around the line
        number indicated by a frame object.
        """
        element = _SourceFragmentElement(
            TagLoader(
                tags.div(
                    tags.span(render="lineNumber"),
                    tags.span(render="sourceLine"),
                    render="sourceLines",
                )
            ),
            self.frame,
        )

        source = [
            " \N{NO-BREAK SPACE} \N{NO-BREAK SPACE}message = " '"This is a problem"',
            " \N{NO-BREAK SPACE} \N{NO-BREAK SPACE}raise Exception(message)",
            "",
        ]
        d = flattenString(None, element)

        stringToCheckFor = ""
        for lineNumber, sourceLine in enumerate(source):
            template = '<div class="snippet{}Line"><span>{}</span><span>{}</span></div>'
            if lineNumber <= 1:
                stringToCheckFor += template.format(
                    ["", "Highlight"][lineNumber == 1],
                    self.base + lineNumber,
                    (" \N{NO-BREAK SPACE}" * 4 + sourceLine),
                )
            else:
                stringToCheckFor += template.format(
                    "", self.base + lineNumber, ("" + sourceLine)
                )

        bytesToCheckFor = stringToCheckFor.encode("utf8")

        d.addCallback(self.assertEqual, bytesToCheckFor)
        return d

    def test_frameElementFilename(self):
        """
        The I{filename} renderer of L{_FrameElement} renders the filename
        associated with the frame object used to initialize the
        L{_FrameElement}.
        """
        element = _FrameElement(TagLoader(tags.span(render="filename")), self.frame)
        d = flattenString(None, element)
        d.addCallback(
            # __file__ differs depending on whether an up-to-date .pyc file
            # already existed.
            self.assertEqual,
            b"<span>" + networkString(__file__.rstrip("c")) + b"</span>",
        )
        return d

    def test_frameElementLineNumber(self):
        """
        The I{lineNumber} renderer of L{_FrameElement} renders the line number
        associated with the frame object used to initialize the
        L{_FrameElement}.
        """
        element = _FrameElement(TagLoader(tags.span(render="lineNumber")), self.frame)
        d = flattenString(None, element)
        d.addCallback(self.assertEqual, b"<span>%d</span>" % (self.base + 1,))
        return d

    def test_frameElementFunction(self):
        """
        The I{function} renderer of L{_FrameElement} renders the line number
        associated with the frame object used to initialize the
        L{_FrameElement}.
        """
        element = _FrameElement(TagLoader(tags.span(render="function")), self.frame)
        d = flattenString(None, element)
        d.addCallback(self.assertEqual, b"<span>lineNumberProbeAlsoBroken</span>")
        return d

    def test_frameElementSource(self):
        """
        The I{source} renderer of L{_FrameElement} renders the source code near
        the source filename/line number associated with the frame object used to
        initialize the L{_FrameElement}.
        """
        element = _FrameElement(None, self.frame)
        renderer = element.lookupRenderMethod("source")
        tag = tags.div()
        result = renderer(None, tag)
        self.assertIsInstance(result, _SourceFragmentElement)
        self.assertIdentical(result.frame, self.frame)
        self.assertEqual([tag], result.loader.load())

    def test_stackElement(self):
        """
        The I{frames} renderer of L{_StackElement} renders each stack frame in
        the list of frames used to initialize the L{_StackElement}.
        """
        element = _StackElement(None, self.failure.frames[:2])
        renderer = element.lookupRenderMethod("frames")
        tag = tags.div()
        result = renderer(None, tag)
        self.assertIsInstance(result, list)
        self.assertIsInstance(result[0], _FrameElement)
        self.assertIdentical(result[0].frame, self.failure.frames[0])
        self.assertIsInstance(result[1], _FrameElement)
        self.assertIdentical(result[1].frame, self.failure.frames[1])
        # They must not share the same tag object.
        self.assertNotEqual(result[0].loader.load(), result[1].loader.load())
        self.assertEqual(2, len(result))

    def test_failureElementTraceback(self):
        """
        The I{traceback} renderer of L{FailureElement} renders the failure's
        stack frames using L{_StackElement}.
        """
        element = FailureElement(self.failure)
        renderer = element.lookupRenderMethod("traceback")
        tag = tags.div()
        result = renderer(None, tag)
        self.assertIsInstance(result, _StackElement)
        self.assertIdentical(result.stackFrames, self.failure.frames)
        self.assertEqual([tag], result.loader.load())

    def test_failureElementType(self):
        """
        The I{type} renderer of L{FailureElement} renders the failure's
        exception type.
        """
        element = FailureElement(self.failure, TagLoader(tags.span(render="type")))
        d = flattenString(None, element)
        exc = b"builtins.Exception"
        d.addCallback(self.assertEqual, b"<span>" + exc + b"</span>")
        return d

    def test_failureElementValue(self):
        """
        The I{value} renderer of L{FailureElement} renders the value's exception
        value.
        """
        element = FailureElement(self.failure, TagLoader(tags.span(render="value")))
        d = flattenString(None, element)
        d.addCallback(self.assertEqual, b"<span>This is a problem</span>")
        return d


class FormatFailureTests(TestCase):
    """
    Tests for L{twisted.web.util.formatFailure} which returns an HTML string
    representing the L{Failure} instance passed to it.
    """

    def test_flattenerError(self):
        """
        If there is an error flattening the L{Failure} instance,
        L{formatFailure} raises L{FlattenerError}.
        """
        self.assertRaises(FlattenerError, formatFailure, object())

    def test_returnsBytes(self):
        """
        The return value of L{formatFailure} is a C{str} instance (not a
        C{unicode} instance) with numeric character references for any non-ASCII
        characters meant to appear in the output.
        """
        try:
            raise Exception("Fake bug")
        except BaseException:
            result = formatFailure(Failure())

        self.assertIsInstance(result, bytes)
        self.assertTrue(all(ch < 128 for ch in result))
        # Indentation happens to rely on NO-BREAK SPACE
        self.assertIn(b"&#160;", result)


class SDResource(resource.Resource):
    def __init__(self, default):
        self.default = default

    def getChildWithDefault(self, name, request):
        d = defer.succeed(self.default)
        resource = util.DeferredResource(d)
        return resource.getChildWithDefault(name, request)


class DeferredResourceTests(SynchronousTestCase):
    """
    Tests for L{DeferredResource}.
    """

    def testDeferredResource(self):
        r = resource.Resource()
        r.isLeaf = 1
        s = SDResource(r)
        d = DummyRequest(["foo", "bar", "baz"])
        resource.getChildForRequest(s, d)
        self.assertEqual(d.postpath, ["bar", "baz"])

    def test_render(self):
        """
        L{DeferredResource} uses the request object's C{render} method to
        render the resource which is the result of the L{Deferred} being
        handled.
        """
        rendered = []
        request = DummyRequest([])
        request.render = rendered.append

        result = resource.Resource()
        deferredResource = DeferredResource(defer.succeed(result))
        deferredResource.render(request)
        self.assertEqual(rendered, [result])

    def test_renderNoFailure(self):
        """
        If the L{Deferred} fails, L{DeferredResource} reports the failure via
        C{processingFailed}, and does not cause an unhandled error to be
        logged.
        """
        request = DummyRequest([])
        d = request.notifyFinish()
        failure = Failure(RuntimeError())
        deferredResource = DeferredResource(defer.fail(failure))
        deferredResource.render(request)
        self.assertEqual(self.failureResultOf(d), failure)
        del deferredResource
        gc.collect()
        errors = self.flushLoggedErrors(RuntimeError)
        self.assertEqual(errors, [])

    def test_legitimateRedirect(self) -> None:
        """
        Legitimate URLs are fully interpolated in the `redirectTo` response body without transformation
        """
        request = DummyRequest([b""])
        html = redirectTo(b"https://twisted.org/", request)
        expected = b"""
<html>
    <head>
        <meta http-equiv=\"refresh\" content=\"0;URL=https://twisted.org/\">
    </head>
    <body bgcolor=\"#FFFFFF\" text=\"#000000\">
    <a href=\"https://twisted.org/\">click here</a>
    </body>
</html>
"""
        self.assertEqual(html, expected)

    def test_maliciousRedirect(self) -> None:
        """
        Malicious URLs are HTML-escaped before interpolating them in the `redirectTo` response body
        """
        request = DummyRequest([b""])
        html = redirectTo(
            b'https://twisted.org/"><script>alert(document.location)</script>', request
        )
        expected = b"""
<html>
    <head>
        <meta http-equiv=\"refresh\" content=\"0;URL=https://twisted.org/&quot;&gt;&lt;script&gt;alert(document.location)&lt;/script&gt;\">
    </head>
    <body bgcolor=\"#FFFFFF\" text=\"#000000\">
    <a href=\"https://twisted.org/&quot;&gt;&lt;script&gt;alert(document.location)&lt;/script&gt;\">click here</a>
    </body>
</html>
"""
        self.assertEqual(html, expected)
