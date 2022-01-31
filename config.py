TOKEN = "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"

PYCURL_SSL_LIBRARY = "openssl"

headers = {
    "Content-Type": "application/json",
    "Authorization": "token " + TOKEN
}

GITHUB_API_URL = "https://api.github.com"

orgs = ["/twitter/repos", "/auth0/repos", "/nasa/repos", "/mozilla/repos", "/adobe/repos"]