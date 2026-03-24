# member_reports.py
from flask import Blueprint, render_template, request, redirect, url_for, session, send_file
import db
import cfs


# Bank details (fixed)
BANK_DETAILS = {"Name of Account": "BSPD",
                "IFSC Code": "SIBL0000722",
                "Bank": "South India Bank",
                "Branch": "Hyderabad" }

CONTRIBUTION_CODES = {  'ChandiHomam': 'CHMA',
                        'BikshaVandanam': 'BVMA',
                        'General': 'GNMA' }


# ── Member Reports Blueprint ────────────────────────────────────────────────
member_reports_bp = Blueprint('member_reports', __name__,)
@member_reports_bp.route('/member_reports', methods=['GET'])
def member_reports_home():
    member_id = request.args.get('member_id', '').strip()
    category = request.args.get('category', '').strip()
    action = request.args.get('action')
    results = []
    error = None

    try:
        if member_id:
            if category == 'contribution':
                results = db.get_contribution_report(member_id, None)
            elif category == 'expenses':
                results = db.get_expenses_report(member_id, None)
            elif category == 'attendance':
                results = db.get_attendance_report(member_id, None)
            elif category == 'recognition':
                results = db.get_recognition_report(member_id, None)
            elif category == 'references':
                results = db.get_references_report(member_id)
            else:
                error = "Select a valid report category."
        elif category:
            error = "Please enter a Member ID to view this report."
    except Exception as e:
        error = str(e)

    if action == 'download':
        if results:
            output = cfs.xls_download (results)

            filename = f"{category}_report_{member_id}.xlsx"

            return send_file(
                output,
                download_name=filename,
                as_attachment=True,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
        else:
            error = f"No data available to download for Member ID {member_id}."

    return render_template('member_reports.html', member_id=member_id, category=category, results=results, error=error)

# ── Member Search Blueprint ─────────────────────────────────────────────────
mbrsearch_bp = Blueprint('mbrsearch', __name__)
@mbrsearch_bp.route('/mbrsearch', methods=['GET', 'POST'])
def member_search():
    if 'user' not in session:
        return redirect(url_for('login'))

    user = session['user']
    member_id = str(user.get('MEMBER_ID')).strip()
    results = []

    # ---------------------------------------------------
    # Check if user is admin
    # ---------------------------------------------------
    is_admin = False
    access = db.get_access_by_member(member_id)
    print(f"\n[DEBUG] Raw access for member_id={member_id}: {access}")

    # Handle both dict and tuple returns
    if access:
        if isinstance(access, dict):
            # Normalize key names
            for k, v in access.items():
                if str(v).strip().upper() == 'Y' and 'ADMIN' in k.upper():
                    is_admin = True
                    break

        elif isinstance(access, (tuple, list)):
            # Convert all values to uppercase strings and check for 'Y'
            for val in access:
                if str(val).strip().upper() == 'Y':
                    is_admin = True
                    break

    print(f"[DEBUG] is_admin for {member_id} = {is_admin}")

    # ---------------------------------------------------
    # Search members
    # ---------------------------------------------------
    if request.method == 'POST':
        criteria = request.form.get('search_query', '').strip()
        if criteria:
            results = db.search_members(criteria)

            # Mask only for non-admins
            if not is_admin:
                for member in results:
                    member["Phone_Num"] = cfs.mask_num(member.get("Phone_Num", "") or "")
                    member["Email_ID"] = cfs.mask_email(member.get("Email_ID", "") or "")

    return render_template('mbrsearch.html', results=results, user=user)

#------------VAN Generator ------------------------------------------
van_bp = Blueprint('van', __name__,)
@van_bp.route('/van', methods=['GET', 'POST'])
def generate_van():
    van_number = None
    bank_details = None
    member_id = None
    contribution_type = None
    error = None

    if request.method == 'POST':
        member_id = request.form.get('member_id', '').strip()
        contribution_type = request.form.get('contribution_type')
        
        if not member_id:
            error = "Please enter a Member ID."
        elif contribution_type not in CONTRIBUTION_CODES:
            error = "Please select a valid contribution type."
        else:
            member_id_padded = str(member_id).zfill(8)
            van_number = f"A345A11{CONTRIBUTION_CODES[contribution_type]}{member_id_padded}"
            bank_details = BANK_DETAILS

    return render_template('van.html', van_number=van_number, bank_details=bank_details,
                           member_id=member_id, contribution_type=contribution_type, error=error, user=session['user'])

