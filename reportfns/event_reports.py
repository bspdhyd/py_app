from flask import Blueprint, render_template, request, session, send_file, flash
import db, cfs, io
import pandas as pd

event_reports_bp = Blueprint('event_reports', __name__)
@event_reports_bp.route('/event_reports/download')
def download_report():
    event_id = request.args.get('event_id', '').strip()
    category = request.args.get('category', '').strip()

    if not event_id or not category:
        return "Event ID and category are required", 400

    try:
        func_map = {'contribution': db.get_contribution_report, 'expenses': db.get_expenses_report,
                    'attendance': db.get_attendance_report, 'recognition': db.get_recognition_report,
                    'registration': db.get_registration_report, }

        if category not in func_map:
            return "Invalid category", 400

        # Get data from DB
        results = func_map[category](member_id=None,event_id=event_id)

        if not results:
            return "No data found for this report", 404

        # Generate Excel file using cfs.xls_download
        output = cfs.xls_download(results)

        return send_file( output, as_attachment=True, download_name=f"{category}_report_event_{event_id}.xlsx",
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' )

    except Exception as e:
        return str(e), 500


@event_reports_bp.route('/event_reports')
def event_reports_home():
    event_id = request.args.get('event_id', '').strip()
    category = request.args.get('category', '').strip()
    results = error = None
    expense_img = contribution_img = None
    total_expense_amount = total_contribution_amount = 0

    user = session.get('user')
    member_id = user['MEMBER_ID'] if user else None

    try:
        if not event_id and category:
            error = "Please enter an Event ID."
        elif event_id:
            if category in ['contribution', 'expenses', 'attendance', 'recognition', 'registration']:
                func_map = {'contribution': db.get_contribution_report, 'expenses': db.get_expenses_report,
                            'attendance': db.get_attendance_report, 'recognition': db.get_recognition_report,
                            'registration': db.get_registration_report, }
                results = func_map[category](member_id=None,event_id=event_id)

            elif category == 'graphs':
                exp = pd.DataFrame(db.get_expenses_by_event(event_id), columns=['Category_ID', 'TotalAmount'])
                con = pd.DataFrame(db.get_contributions_by_event(event_id), columns=['Contribution_Type', 'TotalAmount'])
                exp = exp.groupby('Category_ID')['TotalAmount'].sum().reset_index()
                con = con.groupby('Contribution_Type')['TotalAmount'].sum().reset_index()

                total_expense_amount = exp['TotalAmount'].sum()
                total_contribution_amount = con['TotalAmount'].sum()

                expense_img = cfs.plot_graph( exp['Category_ID'], exp['TotalAmount'],
                                'Category ID', 'Amount', f'Expenses for Event {event_id}' )
                contribution_img = cfs.plot_graph( con['Contribution_Type'], con['TotalAmount'],
                                    'Contribution Type', 'Amount', f'Contributions for Event {event_id}' )
            else:
                error = "Select a valid report category."
    except Exception as e:
        error = str(e)

    return render_template( 'event_reports.html', event_id=event_id, category=category, results=results or [], error=error, user=user,
        expense_img=expense_img, contribution_img=contribution_img, total_expense_amount=total_expense_amount,
        total_contribution_amount=total_contribution_amount )
        

#--------------------Monthly Reports-------------------------------------
monthly_report_bp = Blueprint('monthly_report', __name__)

def generate_monthly_summary(contributions, expenses):
    # Aggregating Sum1 and Sum2 by Month using standard dictionaries
    sum1_by_month = {}
    sum2_by_month = {}
    
    # Accumulate sums
    for item in contributions:
        month = item["Month"]
        if month in sum1_by_month:
            sum1_by_month[month] += item["Amount"]
        else:
            sum1_by_month[month] = item["Amount"]
    
    for item in expenses:
        month = item["Month"]
        if month in sum2_by_month:
            sum2_by_month[month] += item["Amount"]
        else:
            sum2_by_month[month] = item["Amount"]
    
    # Merge results
    merged_array = []
    total_contributions = total_expenses = total_balance = 0

    for month in sorted(set(sum1_by_month.keys()).union(sum2_by_month.keys())):
        contributions = sum1_by_month.get(month, 0)
        expenses = sum2_by_month.get(month, 0)
        balance = contributions - expenses
        # Accumulate totals
        total_contributions += contributions
        total_expenses += expenses
        total_balance += balance
        
        merged_array.append({ "Month": month, "Contributions": contributions,
                        "Expenses": expenses, "Balance": balance  })
        
    merged_array.append({ "Month": "Total", "Contributions": total_contributions,
                "Expenses": total_expenses, "Balance": total_balance  })

    return merged_array

@monthly_report_bp.route('/monthly_report', methods=['GET', 'POST'])
def monthly_report():
    chart_img = None
    error = ""
    start_month = end_month = ""
    merged_array = []
    total_contributions = 0
    total_expenses = 0
    total_balance = 0

    if request.method == 'POST':
        start_month = request.form.get('start_month')
        end_month = request.form.get('end_month')

        if not start_month or not end_month:
             flash("Please select both start and end months.", "warning")
        else:
            try:
                contributions = db.get_contributions_by_month_range(start_month, end_month)
                expenses = db.get_expenses_by_month_range(start_month, end_month)
                df_con = pd.DataFrame(contributions, columns=['Month', 'Type', 'Amount'])
                df_exp = pd.DataFrame(expenses, columns=['Month', 'Type', 'Amount'])

                if df_con.empty and df_exp.empty:
                    flash("No data found for selected months.", "danger")
                else:
                    merged_array = generate_monthly_summary(contributions, expenses)
                        
                    df_con['Source'] = 'Contribution'
                    df_exp['Source'] = 'Expense'
                    df = pd.concat([df_con, df_exp], ignore_index=True)
                    df['Amount'] = pd.to_numeric(df['Amount'], errors='coerce')
                    df.dropna(subset=['Amount', 'Type', 'Month'], inplace=True)

                    chart_img = cfs.plot_double_stacked_bar(df)
            except Exception as e:
                flash(f"Error: {e}", 'danger')

    return render_template('monthly_report.html', chart_img=chart_img, merged_array=merged_array, start_month=start_month, end_month=end_month)


