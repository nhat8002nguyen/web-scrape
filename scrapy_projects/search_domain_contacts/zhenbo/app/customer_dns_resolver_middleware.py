from twisted.internet import defer, reactor
from twisted.names import client, dns
from scrapy import signals


class CustomDNSResolverMiddleware:
    def __init__(self, settings):
        self.resolver = client.createResolver(
            servers=[
                ('8.8.8.8', 53),
                ('208.67.222.222', 53),
                ('9.9.9.9', 53),
                ('1.1.1.1', 53),
                ('45.90.28.0', 53),
                ('8.26.56.26', 53),
                ('192.95.54.3', 53),
                ('185.228.168.168', 53),
            ])  # Use your desired DNS server

    @classmethod
    def from_crawler(cls, crawler):
        o = cls(crawler.settings)
        crawler.signals.connect(o.spider_closed, signal=signals.spider_closed)
        return o

    def process_request(self, request, spider):
        # Use the custom DNS resolver for DNS resolution
        d = self.resolver.getHostByName(request.url)
        d.addCallback(self._handle_dns_response, request)
        return defer.returnValue(d)

    def _handle_dns_response(self, result, request):
        # Update the request with the resolved IP address
        request._set_url(result[0].payload.dottedQuad())

    def spider_closed(self, spider, reason):
        # Clean up the resolver when the spider is closed
        self.resolver.cancelPending()
