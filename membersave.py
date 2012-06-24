#
#	PPAU Member Server processing.
#
from bottle import abort, request, app, static_file, run
from recaptcha.client import captcha
from bbqutils.email import Mailer

import pymongo
from pymongo import Connection

import json
import datetime
import threading

print("Loading Configuration...")
config = json.load(open('config.json', 'r'))
host_ip 	   = config.get('host_ip')        or "localhost"
host_port  	   = config.get('host_port'  )    or 10001
mongodb_server = config.get('mongodb_server') or "localhost"
mongodb_port   = config.get('mongodb_port'  ) or 27017
mail_server    = config.get('mail_server')
mail_user      = config.get('mail_user')
mail_pass      = config.get('mail_pass')
valid_ref      = config.get('valid_ref')      or "http://localhost"
ppau_secretary = config.get('ppau_secretary')

print("Connecting to database at {}:{} ...".format(mongodb_server, mongodb_port))
mongoConnection       = Connection(mongodb_server, mongodb_port)
mongoMemberCollection = mongoConnection.ppau.members	# Database = "ppau". Collection = "members"

print("Reading email templates...")
mail_template_new    = open("mail-new.txt"   , 'r').read()
mail_template_update = open("mail-update.txt", 'r').read()

print("Connecting to mailer at {} ...".format(mail_server))
mailer = Mailer(mail_server, user=mail_user, passwd=mail_pass)
mailer.connect()
print("Done!")


# Threaded email poster
class MailThread(threading.Thread):
	def __init__(self, frm, to, subject, text):
		threading.Thread.__init__(self)
		self.frm = frm
		self.to = to
		self.subject = subject
		self.text = text
	
	def run(self):
		log("server", "Preparing to send email to: %s" % self.to)
		mailer.send_email(self.frm, self.to, subject=self.subject, text=self.text, reply_to=self.frm)
		log("server", "Sent!")

def get_time_now():
	return datetime.datetime.now().strftime("%Y-%m-%d %X")

# Field validation system for client requests
WHY_HERE = "why_are_you_here"
UPDATE_FIELDS = {
	WHY_HERE: [
		"purpose", 
	],
	"details_of_applicant": [
		"date_of_birth",
		"email",
		"gender",
		"given_names",
		"postal_address",
		"primary_phone",
		"secondary_phone",
		"residential_address",
		"surname",
	],
	"submission": [
		"is_declared",
		"recaptcha_challenge_field",
		"recaptcha_response_field",
		"should_be_blank_text",
		"should_be_blank_checkbox",
		"signature",
		"date",
	],
}
NEW_FIELDS = {			
	"declaration_and_membership_requirements": [
		"understand_requirements",
	],
	"other_information": [
		"another_party_checked",
		"opt_out_state_parties_checked",
		"other_party_name",
	],
	"payment": [
		"membership_type",
	],
}
NEW_FIELDS.update(UPDATE_FIELDS)
REQUIRED_FIELDS = {
	"new"    : NEW_FIELDS,
	"update" : UPDATE_FIELDS,
}


ERROR_MISSING    = "missing required field"
ERROR_UNEXPECTED = "unexpected field"
ERROR_VERSION    = "wrong version"
ERROR_INVALID    = "invalid purpose field"
VERSION          = "20120618"

def validate(form):
	# Check for correct version
	if not form.get('version') or form['version'] != VERSION:
		return ERROR_VERSION, form.get('version')

	# Check for existence of relevant subforms
	if WHY_HERE not in form:
		return ERROR_MISSING, WHY_HERE
	purpose = form[WHY_HERE].get('purpose')
	if purpose is None:
		return ERROR_MISSING, 'purpose'
	if purpose not in REQUIRED_FIELDS.keys():
		return ERROR_INVALID, purpose

	# Check that fields and subfields required by subform are present.
	for field, subfields in REQUIRED_FIELDS[purpose].items():
		subform = form.get(field) 
		if subform is None:
			return ERROR_MISSING, field
		if len(subform.keys()) != len(subfields):
			return ERROR_UNEXPECTED, field
	
		for subsubfield in subfields:
			if subform.get(subsubfield) is None:
				return ERROR_MISSING, subsubfield
	
	return None, None


def detect_bot(form):
	return 	form['submission']['should_be_blank_text'] != ""  or \
			form['submission']['should_be_blank_checkbox'] == True


def log(ip, msg):
	print("[%s] (%s) %s" % (get_time_now(), ip, msg))
	return msg


def get_client_ip():
	x_forwarded_for = request.environ.get('HTTP_X_FORWARDED_FOR')
	if x_forwarded_for:
		ip = x_forwarded_for.split(',')[0]
	else:
		ip = request.environ.get('REMOTE_ADDR')
	return ip


app = app()

#=== Enable for Bottle hosting of resoruces and HTML ====
'''
@app.get('/')
def main():
	return open('index.html').read()

@app.get('/<resource>')
def resource(resource):
	try: return open(resource).read()
	except: abort(404) 

@app.post('/app/new_member')
'''
#========================================================

@app.post('/new_member')
def post_new_member():
	
	# Generally log IP address whenever anything funky is detected.
	ip = get_client_ip()

	# Check referrer against configured valid referred
	if not str(request.headers.get('Referer')).startswith(valid_ref):
		log(ip, "invalid referer: %s" % request.headers.get("Referer"))
		return "invalid referer"

	# Extract and validate form	
	form_string = request.forms.get('form')
	form = json.loads(form_string)
	invalid, item = validate(form)
	if invalid:
		log(ip, "%s: %s" % (invalid, item))
		return invalid
	if detect_bot(form):
		return log(ip, "bot detected")

	# Check it's a human
	response = captcha.submit(
		form['submission']['recaptcha_challenge_field'],
		form['submission']['recaptcha_response_field'],
		'6Lcogc8SAAAAAP9yHm-a4M3J6Aqx_kiqZucP8qqE',
		ip
	)
	if not response.is_valid:
		return log(ip, "invalid captcha")

	# Insert member data into database.
	# 		Make sure you have 'journal=true' in mongodb.config file, 
	#		to be sure of durability of insert in single server setup. 
	mongoMemberCollection.insert(form)
	del form['_id']		# MongoDB puts it's own '_id' in the data as inserted
						# It's doesn't serialize too well by default.
						# We're not using it though, so get rid of it for now.	

	# Kick off appropriate confirmation email
	given_names = form['details_of_applicant']['given_names']
	surname		= form['details_of_applicant']['surname']
	email		= form['details_of_applicant']['email']
	state		= form['details_of_applicant']['residential_address']['state']
	template = None
	if form[WHY_HERE]['purpose'] == "new":
		template = mail_template_new
		subject = "Membership Application Received"
		log(ip, "New member: %s %s [%s] (%s)" % (
			given_names, surname, email, state
		))
	elif form[WHY_HERE]['purpose'] == "update":
		template = mail_template_update
		subject = "Membership Details Update Received"
		log(ip, "Updated member: %s %s [%s] (%s)" % (
			given_names, surname, email, state
		))
	
	# Start threaded  email transmission
	if template is not None:
		MailThread(
			ppau_secretary,
			"%s %s <%s>" % (given_names, surname, email),
			subject,
			template.format(given_names=given_names, surname=surname)
		).start()

	return form

if __name__ == "__main__":
	run(app, server="cherrypy", host=host_ip, port=host_port)
	