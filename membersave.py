from bottle import abort, request, app, static_file, run
from elixir import *
from recaptcha.client import captcha
from bbqutils.email import Mailer

import json
import datetime
import threading

metadata.bind = "sqlite:///raw_member_data.db"
#metadata.bind.echo = True


class MemberData(Entity):
	using_options(tablename='raw_member_data')
	data = Field(UnicodeText)


VALID_REF = "https://join.pirateparty.org.au"
#VALID_REF = "http://localhost"
VERSION = "20120520"
MAIL_USER = "FILL ME"
MAIL_PASS = "FILL ME"

mailer = Mailer("smtp.gmail.com", 
	user=MAIL_USER,
	passwd=MAIL_PASS
)
print("Connecting to mailer...")
mailer.connect()
mail_template = open("mail.txt", 'r').read()
print("Done!")


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


def validate(obj):
	# Check for correct version
	if not obj.get('version') or obj['version'] != VERSION:
		return "wrong version", None

	# Check for existence of relevant subforms
	for k, v in {
			"details_of_applicant": 9,
			"declaration_and_membership_requirements": 1,
			"other_information": 3,
			"payment_and_submission": 7
	}.items():
		if obj.get(k) is None:
			return "missing required field", k
		if len(list(obj[k].keys())) != v:
			return "unexpected fields", k
	
	for k in (
		"date_of_birth",
		"email",
		"gender",
		"given_names",
		"postal_address",
		"primary_phone",
		"secondary_phone",
		"residential_address",
		"surname"
	):
		if obj['details_of_applicant'].get(k) is None:
			return "missing required field", k
		
	for k in (
		"understand_requirements",
	):
		if obj['declaration_and_membership_requirements'].get(k) is None:
			return "missing required field", k

	for k in (
		"another_party_checked",
		"opt_out_state_parties_checked",
		"other_party_name"
	):
		if obj['other_information'].get(k) is None:
			return "missing required field", k
	
	for k in (
		"is_declared",
		"membership_type",
		"recaptcha_challenge_field",
		"recaptcha_response_field",
		"should_be_blank_text",
		"should_be_blank_checkbox",
		"signature"
	):
		if obj['payment_and_submission'].get(k) is None:
			return "missing required field", k
	
	return None, None


def detect_bot(obj):
	return obj['payment_and_submission']['should_be_blank_text'] != "" or \
		obj['payment_and_submission']['should_be_blank_checkbox'] == True


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
"""
@app.get('/')
def main():
	return open('index.html').read()

@app.get('/<resource>')
def resource(resource):
	return open(resource).read()
"""

@app.post('/new_member')
def post_new_member():
	session.remove()

	ip = get_client_ip()
	if not str(request.headers.get('Referer')).startswith(VALID_REF):
		log(ip, "invalid referer: %s" % request.headers.get("Referer"))
		return "invalid referer"
	
	form_string = request.forms.get('form')
	form = json.loads(form_string)
	
	invalid, item = validate(form)
	if invalid:
		log(ip, "%s: %s" % (invalid, item))
		return invalid
	
	if detect_bot(form):
		return log(ip, "bot detected")

	response = captcha.submit(
		form['payment_and_submission']['recaptcha_challenge_field'],
		form['payment_and_submission']['recaptcha_response_field'],
		'6Lcogc8SAAAAAP9yHm-a4M3J6Aqx_kiqZucP8qqE',
		ip
	)
	if not response.is_valid:
		return log(ip, "invalid captcha")

	d = MemberData(data=json.dumps(form))
	session.add(d)
	session.commit()

	given_names = form['details_of_applicant']['given_names']
	surname = form['details_of_applicant']['surname']
	email = form['details_of_applicant']['email']

	MailThread(
		"Brendan Molloy <secretary@pirateparty.org.au>",
		"%s %s <%s>" % (given_names, surname, email),
		"Membership Application Received",
		mail_template.format(given_names=given_names, surname=surname)
	).start()

	log(ip, "New member: %s %s [%s]" % (
		form['details_of_applicant']['given_names'],
		form['details_of_applicant']['surname'],
		form['details_of_applicant']['email']
	))
	return form


if __name__ == "__main__":
	setup_all()
	create_all()
	run(app, server="cherrypy", host="127.0.0.1", port=10001)

