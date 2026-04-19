from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
import db
from datetime import date

manual_contribution_bp = Blueprint('manual_contribution', __name__, url_prefix='/manual_contribution')

SCREEN_PASSWORD = 'kamakoti2026'


@manual_contribution_bp.route('/', methods=['GET', 'POST'])
def manual_contribution():
    if 'user' not in session:
        return redirect(url_for('login'))

    # Screen-level password gate (persisted in session)
    if not session.get('manual_contrib_auth'):
        if request.method == 'POST' and request.form.get('action') == 'verify_password':
            if request.form.get('screen_password') == SCREEN_PASSWORD:
                session['manual_contrib_auth'] = True
            else:
                flash("Incorrect password.", "danger")
                return render_template('manual_contribution.html', pw_required=True)
        else:
            return render_template('manual_contribution.html', pw_required=True)

    deshcodes = db.get_desh_codes()
    events = db.get_open_events_for_contribution()
    today = date.today().strftime('%Y-%m-%d')

    active_tab = 'insert'
    new_transaction_code = None
    new_amt_in_words = None
    contributions = []
    filter_vals = {'deshcode': '', 'event_id': '', 'transaction_code': '', 'date_from': '', 'date_to': ''}

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'create':
            active_tab = 'insert'
            try:
                tc = db.create_manual_contribution(
                    request.form.get('deshcode', 'BHBNR001'),
                    request.form.get('event_id'),
                    request.form.get('member_id'),
                    request.form.get('amount'),
                    request.form.get('contribution_type', 'CHEQUE'),
                    request.form.get('contribution_date'),
                    request.form.get('reference_details', ''),
                    request.form.get('receipt_pdf_url', ''),
                    request.form.get('approved', 'Y')
                )
                receipt = db.get_receipt_data(tc)
                if receipt:
                    new_transaction_code = receipt.get('Transaction_Code', tc)
                    new_amt_in_words = receipt.get('Amount_In_Words', '')
                else:
                    new_transaction_code = tc
                flash(f"Contribution saved. Transaction Code: {new_transaction_code}", "success")
            except Exception as e:
                flash(f"Error saving contribution: {str(e)}", "danger")

        elif action in ('search_update', 'update'):
            active_tab = 'update'
            filter_vals = {
                'deshcode': request.form.get('filter_deshcode', ''),
                'event_id': request.form.get('filter_event_id', ''),
                'transaction_code': request.form.get('filter_transaction_code', ''),
                'date_from': request.form.get('filter_date_from', ''),
                'date_to': request.form.get('filter_date_to', '')
            }

            if action == 'update':
                try:
                    db.update_manual_contribution(
                        request.form.get('upd_transaction_code'),
                        request.form.get('upd_amount'),
                        request.form.get('upd_contribution_type'),
                        request.form.get('upd_contribution_date'),
                        request.form.get('upd_reference_details', ''),
                        request.form.get('upd_receipt_pdf_url', ''),
                        request.form.get('upd_approved', 'Y')
                    )
                    flash(f"Contribution {request.form.get('upd_transaction_code')} updated successfully.", "success")
                except Exception as e:
                    flash(f"Error updating: {str(e)}", "danger")

            contributions = db.get_contributions_for_manual_update(
                filter_vals['deshcode'] or None,
                filter_vals['event_id'] or None,
                filter_vals['transaction_code'] or None,
                filter_vals['date_from'] or None,
                filter_vals['date_to'] or None
            )

    return render_template('manual_contribution.html',
        pw_required=False,
        deshcodes=deshcodes,
        events=events,
        today=today,
        active_tab=active_tab,
        new_transaction_code=new_transaction_code,
        new_amt_in_words=new_amt_in_words,
        contributions=contributions,
        filter_vals=filter_vals
    )


@manual_contribution_bp.route('/member_search')
def member_search():
    if 'user' not in session:
        return jsonify([])
    term = request.args.get('q', '').strip()
    if len(term) < 2:
        return jsonify([])
    members = db.search_members_for_contribution(term)
    return jsonify(members)
