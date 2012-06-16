""" Register for your free reCAPTCHA Mailhide Public/Private API keys here: http://www.google.com/recaptcha/Mailhide/
	
	NOTE: The mailhide.py module uses "reCAPTCHA Mailhide" API keys, NOT "reCAPTCHA" 
	API keys. Both are separate API's and both use different, incompatible keys.
	
	NOTE: You must install the Crypto Python library to use mailhide.py. Otherwise 
	an exception will be raised when you import mailhide.py.
	
	Crypto Website: http://cheeseshop.python.org/pypi/pycrypto/
	
	Crypto Installation with PIP:
		$ sudo pip install pycrypto
		...installs...
		$ python
		>>> import Crypto
		>>> Crypto
		<module 'Crypto' from '.../site-packages/Crypto/__init__.pyc'>
	
	
	General usage pattern:
	
	1) from recaptcha.client.mailhide import ashtml
	2) Generate reCAPTCHA Mailhide HTML via ashtml(), passing the email address you want to hide along with API keys.
	3) Render generated HTML into your webpage.
	4) Display webpage for user.
	5) User see's your abridged email like so: "mike...@example.com"
	6) When user clicks on abridged email, a reCAPTCHA window pops-up.
	7) If user solves reCAPTCHA in pop-up window, your full email address is displayed.
	
	See comments inside ashtml() for more details, and additional arguments/options 
	which can be passed. You can also specify to use SSL when contacting the 
	reCAPTCHA Mailhide servers.
"""

import base64
import cgi

try:
	from Crypto.Cipher import AES
except:
	raise Exception("You need the pycrpyto library: http://cheeseshop.python.org/pypi/pycrypto/")

MAIL_HIDE_BASE		= "http://www.google.com/recaptcha/mailhide"
MAIL_HIDE_BASE_SSL	= "https://www.google.com/recaptcha/mailhide"


def asurl(email, public_key, private_key, use_ssl=False):
	""" Wraps an email address with reCAPTCHA Mailhide and returns the URL.
		
		
		_____Return Value_____
		
		- URL for reCAPTCHA Mailhide server.
		- Raises exception if |public_key| or |private_key| are not encoded properly.
		
		
		_____Parameters_____
		
		email 		- Email you want to create the reCAPTCHA Mailhide URL for.
		public_key 	- Your Public reCAPTCHA Mailhide API Key (base 64 encoded)
		private_key	- Your Private reCAPTCHA Mailhide API Key (AES, 32 hex characters).
		use_ssl		- If True, generated reCAPTCHA Mailhide URL uses SSL.
		
		
		_____Discussion_____
		
		Using SSL is recommended to hide your Private API key, and to 
		hide your revealed email address from certain man-in-the-middle 
		attacks.
		
		HINT: If you copy/paste the |public_key| and |private_key| keys from 
		the reCAPTCHA Mailhide website, they'll be in the proper encoding/format.
	"""
	
	if use_ssl:
		base_url = MAIL_HIDE_BASE_SSL
	else:
		base_url = MAIL_HIDE_BASE
	
	cryptmail	= _encrypt_string(email, base64.b16decode(private_key, casefold=True), '\0' * 16)
	base64crypt = base64.urlsafe_b64encode(cryptmail)
	
	return "%s/d?k=%s&c=%s" % (base_url, public_key, base64crypt)


def ashtml(email, public_key, private_key, use_ssl=False):
	""" Wraps an email address with reCAPTCHA Mailhide and returns HTML 
		to display the email address, abridged, with a link to open a 
		reCAPTCHA pop-up window. If the user clicks on the link and 
		solves the reCAPTCHA, the full email address is displayed.
		
		
		_____Return Value_____
		
		- HTML for reCAPTCHA Mailhide server. Place it on your webpage.
		- Internally called asurl() will raise exception if |public_key| or |private_key| are not encoded properly.
		
		
		_____Parameters_____
		
		email 		- Email you want to create the reCAPTCHA Mailhide URL for.
		public_key 	- Your Public reCAPTCHA Mailhide API Key (base 64 encoded)
		private_key	- Your Private reCAPTCHA Mailhide API Key (AES, 32 hex characters).
		use_ssl		- If True, generated HTML uses the SSL reCAPTCHA Mailhide URL.
		
		
		_____Discussion_____
		
		Using SSL is recommended to hide your Private API key, and to 
		hide your revealed email address from certain man-in-the-middle 
		attacks.
		
		HINT: If you copy/paste the |public_key| and |private_key| keys from 
		the reCAPTCHA Mailhide website, they'll be in the proper encoding/format.
	"""
	
	url = asurl(email, public_key, private_key, use_ssl)
	(userpart, domainpart) = _doterizeemail(email)
	
	html = """%(user)s<a href="%(url)s" onclick="window.open('%(url)s', '', 'toolbar=0,scrollbars=0,location=0,statusbar=0,menubar=0,resizable=0,width=500,height=300'); return false;" title="Reveal this e-mail address">...</a>@%(domain)s""" % {
		'user':		cgi.escape(userpart),
		'url':		cgi.escape(url),
		'domain':	cgi.escape(domainpart),
		}
	
	return html


def _pad_string(str, block_size):
	numpad = block_size - (len(str) % block_size)
	return str + numpad * chr(numpad)


def _encrypt_string(str, aes_key, aes_iv):
	if len(aes_key) != 16:
		raise Exception("expecting key of length 16")
	if len(aes_iv) != 16:
		raise Exception("expecting iv of length 16")
	return AES.new(aes_key, AES.MODE_CBC, aes_iv).encrypt(_pad_string(str, 16))


def _doterizeemail(email):
	""" Splits an email address into two parts, split at '@', 
		and abridges the local-part of local-part@domain.com.
		The returned tuple can be used to display an abridged 
		email address without revealing it in full.
		
		johnsmith@example.com ---> ('john', 'example.com')
		
		
		_____Return Value_____
		
		- |email| split into an abridged local-part, and domain-part, as Tuple.
	"""
	
	try:
		[user, domain] = email.split('@')
	except:
		# handle invalid emails... sorta
		user = email
		domain = ""
	
	if len(user) <= 4:
		user_prefix = user[:1]
	elif len(user) <= 6:
		user_prefix = user[:3]
	else:
		user_prefix = user[:4]
	
	return (user_prefix, domain)
