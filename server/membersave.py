#
#    PPAU Member Server processing.
#
from bottle import abort, request, app, static_file, run
from recaptcha.client import captcha
from bbqutils.email import Mailer

import pymongo
from pymongo import Connection

import json
import datetime
import time
import threading
import uuid

print("Loading Configuration...")
config = json.load(open('config.json', 'r'))
host_ip = config.get('host_ip') or "localhost"
host_port = config.get('host_port') or 10001
mongodb_server = config.get('mongodb_server') or "localhost"
mongodb_port = config.get('mongodb_port') or 27017
mail_server = config.get('mail_server') or "localhost"
mail_user = config.get('mail_user') or None
mail_pass = config.get('mail_pass') or None
valid_ref = config.get('valid_ref') or "http://localhost"
ppau_secretary = config.get('ppau_secretary')
inform_secretary = config.get('inform_secretary') or False 

print("Connecting to database at {}:{}...".format(mongodb_server, mongodb_port))
mongo_connection = Connection(mongodb_server, mongodb_port)
mongo_member_collection = mongo_connection.ppau.members    # Database = "ppau". Collection = "members"

print("Reading email templates...")
mail_template_new = open("mail-new.txt", 'r').read()
mail_template_update = open("mail-update.txt", 'r').read()

print("Connecting to mailer at {}...".format(mail_server))
mailer = Mailer(mail_server, user=mail_user, passwd=mail_pass)
mailer.connect()
print("Done!")


MAX_AUTO_RECONNECT_ATTEMPTS = 5
def mongo_safe_insert(collection, data):
    '''
    Insert member data into database and wait for commit.
    Attempt auto-reconnect on failure.    
    
    1. Make sure you have 'journal=true' in mongodb.config file, 
       to be sure of durability of insert in single server setup.
    2. safe=True makes us wait for the journalled DB to commit. 
       If it fails to commit other than connection issues, 
               OperationFailure exception is detected and we return False immediately.
    3. If it fails to commit due to connection issues, 
            AutoReconnect exception is detected and we retry with exponential backoff.
            Atter MAX_AUTO_RECONNECT_ATTEMPTS connect issues, give up and return False.
     '''
    for attempt in range(MAX_AUTO_RECONNECT_ATTEMPTS):
        try:
            collection.insert(data, safe=True)
            return True
        except pymongo.errors.OperationFailure:
            return False
        except pymongo.errors.AutoReconnect as e:
            wait_t = 0.5 * pow(2, attempt) # exponential back off
            log("server", "PyMongo auto-reconnecting... {}. Waiting {} seconds.".format(str(e), wait_t))
            time.sleep(wait_t)
    return False

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
VERSION          = "20120924"

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
    return form['submission']['should_be_blank_text'] != ""  or \
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

@app.get('/confirm/<uuid>')
def get_confirm(uuid):
    ip = get_client_ip()
    
    if uuid is None:
        log(ip, "null uuid")
        abort(404)
    
    o = {
        "why_are_you_here": { "purpose": "confirm" },
        "details_of_applicant": { "uuid": uuid }
    }
    
    if not mongo_safe_insert(mongo_member_collection, o):
        log(ip, "database error")
        abort(500)
    
    log(ip, uuid + " has confirmed.")
    return static_file("confirm.html", root="../client") 


@app.get('/update/<uuid>')
@app.get('/update')
@app.get('/new')
@app.get('/')
def get_main(uuid=None):
    return static_file("index.html", root="../client")


@app.get('/resign/<uuid>')
def get_resign_member(uuid):
    return static_file("resign.html", root="../client")    


@app.post('/resign/<uuid>')
def post_resign_member(uuid=None):
    ip = get_client_ip()
    
    if uuid is None:
        log(ip, "null uuid")
        abort(404)
    
    o = {
        "why_are_you_here": { "purpose": "resign" },
        "details_of_applicant": { "uuid": uuid }
    }
    
    if not mongo_safe_insert(mongo_member_collection, o):
        log(ip, "database error")
        abort(500)
    
    log(ip, uuid + " has resigned.")
    return "You have been resigned. Thanks!"


@app.get('/<resource>')
def resource(resource):
    return static_file(resource, root="../client")


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

    # Add UUID to new member
    if form[WHY_HERE]['purpose'] == "new":    
        form['details_of_applicant']['uuid'] = uuid.uuid4().hex

    # Make robust ttempt to insert member data into database.
    if not mongo_safe_insert(mongo_member_collection, form):
        return log(ip, "database error")
    
    # MongoDB puts it's own '_id' in the data as inserted
    # It's doesn't serialize too well by default.
    # We're not using it though, so get rid of it for now.
    # Laterm use json_util to sort this out.
    del form['_id']            

    # Kick off appropriate confirmation email
    given_names = form['details_of_applicant']['given_names']
    surname = form['details_of_applicant']['surname']
    email = form['details_of_applicant']['email']
    state = form['details_of_applicant']['residential_address']['state']
    
    template = None
    if form[WHY_HERE]['purpose'] == "new":
        template = mail_template_new
        subject = "Membership Application Received"
        msg = log(ip, "New member: %s %s [%s] (%s)" % (
            given_names, surname, email, state
        ))
    elif form[WHY_HERE]['purpose'] == "update":
        template = mail_template_update
        subject = "Membership Details Update Received"
        msg = log(ip, "Updated member: %s %s [%s] (%s)" % (
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

        if form[WHY_HERE]['purpose'] == "update":
            x = []
            for k, v in form['details_of_applicant'].items():
                x.append("%s: %s" % (k, v))
            x = "\n".join(x)
            
            MailThread(
                email,
                "membership@support.pirateparty.org.au",
                "Updated member: %s %s" % (given_names, surname),
                x
            ).start()

    if inform_secretary:
        MailThread(
            ppau_secretary,
            ppau_secretary,
            "%s %s" % (msg, ip),
            form['details_of_applicant']['uuid']
        ).start()

    return form

if __name__ == "__main__":
    run(app, server="cherrypy", host=host_ip, port=host_port)
    
