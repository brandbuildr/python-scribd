"""
Example: user.py

Signing in as a scribd.com user and accessing users's documents.
"""

import logging

import scribd


# Set your API key and secret here.
API_KEY = ''
API_SECRET = ''

# Set to the scribd.com user credentials.
USERNAME = ''
PASSWORD = ''


# Uncomment to enable scribd package debugging.
#logging.basicConfig(level=logging.DEBUG)


def main():
    # Configure the Scribd API.
    scribd.config(API_KEY, API_SECRET)

    try:
        # Log the user in.
        user = scribd.login(USERNAME, PASSWORD)
        
        # Get all documents uploaded by the user.
        docs = user.all()

        print 'User %s has %d documents.' % (user.username, len(docs))
        if docs:
            print "User's documents:"
            for doc in docs:
                print '*', doc.title
                
        # Search the user documents for the phrase "checklist".
        results = user.find('checklist')
        
        print 'Search for "checklist" turned up %d results:' % len(results)
        for doc in results:
            print '*', doc.title

    except scribd.ResponseError, err:
        print 'Scribd failed: code=%d, error=%s' % (err.errno, err.strerror)


if __name__ == '__main__':
    main()
