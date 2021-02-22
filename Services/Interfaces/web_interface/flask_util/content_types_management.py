import mimetypes


def init_content_types():
    # force mimetypes not to rely on system configuration
    mimetypes.add_type('text/css', '.css')
    mimetypes.add_type('application/javascript', '.js')
    mimetypes.add_type('image/x-icon', '.ico')
    mimetypes.add_type('image/svg+xml', '.svg')
    mimetypes.add_type('font/woff2', '.woff2')
    mimetypes.add_type('font/woff2', '.woff2')
