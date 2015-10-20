import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), "lib/pyxl/"))

s = """
#coding: pyxl
from pyxl import html, rss
channel = (
    <frag>
        <rss.rss_decl_standalone />
        <rss.rss version="2.0">
            <rss.channel>
                <rss.title>A Title</rss.title>
                <rss.link>https://www.dropbox.com</rss.link>
                <rss.description>A detailed description</rss.description>
                <rss.ttl>60</rss.ttl>
                <rss.language>en-us</rss.language>
            </rss.channel>
        </rss.rss>
    </frag>
)

for i in xrange(60000):
    channel.to_string()
"""

from pyxl.codec.register import pyxl_transform_string
t = pyxl_transform_string(s)

exec s
