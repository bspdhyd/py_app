# main.py
import os
from dotenv import load_dotenv

load_dotenv()

from flask import Flask, render_template, request, redirect, url_for, session, flash
import db, cfs, subprocess
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

#Importing blueprints of each function/screen
from cflskrtn import cflskrtn_bp
from crudfns.events import events_bp  
from updatefns.attendence import attendence_bp  
from crudfns.registration import registration_bp  
from crudfns.expenses import expenses_bp  
from crudfns.contribution import contribution_bp
from reportfns.member_reports import member_reports_bp, mbrsearch_bp, van_bp
from reportfns.event_reports import event_reports_bp, monthly_report_bp
from updatefns.nwmember import nwmember_bp
from schools.podili_assignment import podili_assignment_bp
from schools.podili_admission import podili_admission_bp
from crudfns.password_modify import password_bp
from updatefns.access import access_bp
from updatefns.qrcode_gen import qrcode_bp
from reportfns.master_data import master_data_bp
from reportfns.multiple_data import multiple_data_bp
from updatefns.update_member import update_member_bp
from crudfns.requests import requests_bp
from reportfns.issues import issues_bp, referer_issues_bp
from reportfns.sibcollection_report import sibcollection_report_bp
from research.images import images_bp
from updatefns.dupidentifier import dupidentifier_bp
from crudfns.payee import payee_bp
from crudfns.payee_acc import payee_acc_bp
from updatefns.conf_payment import conf_payment_bp
from updatefns.vmt_details import vmt_bp, vamsatree_bp
from NBV.nbv_subcollector import nbv_subcollector_bp
from crudfns.manual_contribution import manual_contribution_bp
from publicfns.bv_stats import bv_stats_bp


blueprints = [cflskrtn_bp, events_bp, attendence_bp, registration_bp, expenses_bp, mbrsearch_bp, contribution_bp, van_bp, member_reports_bp, event_reports_bp, nwmember_bp, podili_assignment_bp, podili_admission_bp, password_bp, vamsatree_bp, access_bp, qrcode_bp, master_data_bp, multiple_data_bp, update_member_bp, requests_bp, monthly_report_bp, issues_bp, sibcollection_report_bp, referer_issues_bp, images_bp, dupidentifier_bp, payee_bp, payee_acc_bp, conf_payment_bp, vmt_bp, nbv_subcollector_bp, manual_contribution_bp, bv_stats_bp]

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev_secret_key")

for blueprint in blueprints:
    app.register_blueprint(blueprint)


@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    message = None
    if request.method == 'POST':
        member_id = request.form['MEMBER_ID']
        password = request.form['Password']
        user = db.get_user_by_credentials(member_id, password)
        if user:
            session['user'] = user
            session['entity_id'] = request.form['entity_id']
            usraccess = db.get_access_by_member(member_id)
            session['access'] = usraccess
            logger.info(f"User {member_id} logged in successfully.")
            return redirect(url_for('dashboard'))
        else:
            message = 'Invalid Member ID or Password.'
            logger.warning(f"Failed login attempt for {member_id}.")
    return render_template('login.html', message=message)

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    otp = cfs.generate_complex_otp(6)
    
    ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
    logid = session['user']['MEMBER_ID']
    db.create_tokens(logid, ip_address)
    
    testvalue = 'Testing'
    key = 'PayeeBankAccountNumber'
    encryptvalue = cfs.encrypt_details(testvalue, key)
    decryptvalue = cfs.decrypt_details(encryptvalue, key)
    
    fevents = db.get_future_events()
    
    payee = db.get_payee_details(logid)
    acctnum = 0
    enacctnum = 0
#    if payee:
#        acct_num = payee['Payee_Acnt_Num']
#        result = subprocess.run(['php', 'phpcfs.php', "decrypt", acct_num, key], capture_output=True, text=True)
#        acctnum = result.stdout.strip()
#        eresult = subprocess.run(['php', 'phpcfs.php', "encrypt", acctnum, key], capture_output=True, text=True)
#        enacctnum = eresult.stdout.strip()

    return render_template('dashboard.html', otp=otp, ip_address=ip_address, user=session['user'], usraccess=session['access'], encryptvalue=encryptvalue, decryptvalue=decryptvalue, acctnum=acctnum, enacctnum=enacctnum, fevents=fevents)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

#for rule in app.url_map.iter_rules():
   # print(rule)
if __name__ == '__main__':
    app.run(debug=True)
