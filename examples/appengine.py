"""
Example: appengine.py

This is a simple Google App Engine example using the scribd library.

It uses the App Enigne's default webapp framework to create two simple pages.
First one (accessed using "/" path), created in the Form class, lists all documents
belonging to the Scribd API account user. A file upload form is placed under the list
on the webpage. The form sends the file to the second page ("/upload"), created in
the Upload class.

The upload page extracts the file from the request and sends it to the scribd library
for uploading to the Scribd platform. This is immediately followed by redirection to
the first page which at this point will list the freshly uploaded file among other
documents.
"""

from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app

import scribd


# Set your API key and secret here.
API_KEY = ''
API_SECRET = ''


class Form(webapp.RequestHandler):
    """Creates the main page displaying documents and allowing to upload new ones."""
    
    def get(self):
        out = []
        
        # Start the document.
        out.append('<html><body>')

        # Start the table.
        out.append('<table border="3">')

        # Add the table header.
        out.append("""
            <tr>
                <td>Status</td>
                <td>Thumbnail</td>
                <td>Title</td>
                <td>Description</td>
            </tr>
        """)
        
        # List all API user documents.
        for doc in scribd.api_user.xall():
            # Substitution dictionary.
            args = {'status': doc.conversion_status,
                    'thumbnail': doc.thumbnail_url,
                    'link': doc.get_scribd_url(),
                    'title': doc.title,
                    'description': doc.description}
            # Add table row.
            out.append("""
                <tr>
                    <td>%(status)s</td>
                    <td><a href="%(link)s"><img src="%(thumbnail)s" border="0"></a></td>
                    <td><a href="%(link)s">%(title)s</a></td>
                    <td><pre>%(description)s</pre></td>
                </tr>
            """ % args)

        # End the table.        
        out.append('</table>')
        
        # Add file form for uploading.
        out.append("""
            <form method="post" enctype="multipart/form-data" action="/upload">
                <input type="file" name="file" /><br/>
                <textarea name="description" cols="30" rows="4">Description</textarea><br/>
                <input type="submit" />
                <input type="reset" />
            </form>
        """)

        # End the document.        
        out.append('</body></html>')

        self.response.out.write('\n'.join(out))


class Upload(webapp.RequestHandler):
    """Passes the uploaded file to Scribd and redirects back to the main page."""
    
    def post(self):
        # Get the cStringIO object containing the file data.
        file = self.request.POST.get('file').file
        
        # Get the name of the uploaded file.
        name = self.request.POST.get('file').filename
        
        # Upload the file to Scribd.
        document = scribd.api_user.upload(file, name, access='private')
        
        # Set the description.
        document.description = self.request.get('description')
        document.save()

        # Redirect back to the main page.
        self.redirect('/')


application = webapp.WSGIApplication([
        ('/', Form),
        ('/upload', Upload),
    ], debug=True)


if __name__ == '__main__':
    # Set the Scribd API key and API secret.
    scribd.config(API_KEY, API_SECRET)
    
    # Start the application.
    run_wsgi_app(application)
