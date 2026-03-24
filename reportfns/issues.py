# issues.py
from flask import Blueprint, render_template, request
import db

# ── Issues Blueprint ────────────────────────────────────────────────────────
issues_bp = Blueprint('issues', __name__)
@issues_bp.route('/issues', methods=['GET', 'POST'])
def view_issues():
    selected_filter = None
    issues = []

    if request.method == 'POST':
        selected_filter = request.form.get('issue_type')

        if selected_filter == 'status':
            issues = db.get_members_with_status_issues()
        elif selected_filter == 'referrer':
            issues = db.get_members_with_referrer_issues()
        elif selected_filter == 'birthyear':
            issues = db.get_members_with_birthyear_issues()
        elif selected_filter == 'surname':
            issues = db.get_members_with_surname_issues()
        elif selected_filter == 'nocontrib':
            issues = db.get_members_with_no_contributions()

    return render_template('issues.html', issues=issues, selected_filter=selected_filter)

# ── Referer Issues Blueprint ────────────────────────────────────────────────
referer_issues_bp = Blueprint('referer_issues', __name__)

@referer_issues_bp.route('/referer_issues', methods=['GET', 'POST'])
def referer_issues():
    data = []
    error_type = ""
    name = ""

    if request.method == 'POST':
        member_id = request.form.get('Member_id')
        error_type = request.form.get('Search')

        try:
            member = db.get_member_data(member_id)
            if member:
                name = member['Alias']
                if error_type == 'YrBirth':
                    data = db.get_yob_issues(member_id)
                elif error_type == 'Surname':
                    data = db.get_surname_issues(member_id)
                elif error_type == 'AddrIssue':
                    data = db.get_address_issues(member_id)
                elif error_type == 'ParentData':
                    data = db.get_parent_issues(member_id)
                elif error_type == 'DupIssue':
                    data = db.get_duplicate_issues(member_id)
            else:
                name = "Invalid Member"
        except Exception as e:
            name = f"Error occurred: {str(e)}"

    return render_template('referer_issues.html', data=data, error_type=error_type, name=name)
