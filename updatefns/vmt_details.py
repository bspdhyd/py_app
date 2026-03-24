from flask import Blueprint, render_template, request, redirect, url_for, flash, session
import db

vmt_bp = Blueprint('vmt', __name__)
# ------------------- VIEW PAGE -------------------
@vmt_bp.route('/vmt-details', methods=['GET', 'POST'])
def view_vmt_details():

    # RESET
    if request.args.get("reset") == "1":
        session.pop("last_search", None)
        return render_template("vmt_details.html", members=[])

    # PREVIOUS SEARCH
    if request.method == "GET" and "last_search" in session:
        search_query = session["last_search"]
    else:
        search_query = request.form.get("search", "").strip()

    # NO SEARCH → show logged in user
    if not search_query:
        if "user" not in session:
            flash("Session expired. Please login again.", "danger")
            return redirect(url_for("login"))

        member = db.get_vmt_member_by_id(session["user"]["MEMBER_ID"])
        return render_template("vmt_details.html", members=[member] if member else [])

    session["last_search"] = search_query

    # PROCESS TOKEN LIST
    terms = [t.strip() for t in search_query.replace(",", " ").split() if t.strip()]

    members = db.search_vmt_members(terms)

    return render_template("vmt_details.html", members=members)


# ------------------- SAVE ALL MEMBERS -------------------
@vmt_bp.route('/vmt-details/update-all', methods=['POST'])
def update_all_vmt_members():

    member_ids = request.form.getlist("member_id[]")
    fathers = request.form.getlist("father[]")
    mothers = request.form.getlist("mother[]")
    spouses = request.form.getlist("spouse[]")
    referrers = request.form.getlist("referrer[]")

    for i in range(len(member_ids)):

        db.update_vmt_member( member_ids[i], fathers[i],
            mothers[i], spouses[i], referrers[i] )

    flash("All members updated successfully!", "success")
    return redirect(url_for("vmt.view_vmt_details"))

#-------VamsaTree ----------------------------------------------------
vamsatree_bp = Blueprint('vamsatree', __name__,)

@vamsatree_bp.route('/vamsatree', methods=['GET', 'POST'])
def family_tree_page():
    
    if request.method == 'POST':
        member_id = request.form.get('search_id')
    else:
        member_id = session['user']['MEMBER_ID']
    
    memdata = db.get_member_data(member_id)

    root = root_id(member_id)
    
    colors = ["aqua", "yellow", "#ff9999", "#90EE90", "#FFD580", "#ff80ff",
              "#ff3377", "#aa80ff", "navy", "olive", "purple", "red", "silver", "teal", "white", "yellow"]
    
    family_tree_data = build_family_tree(root, 0, colors)

    return render_template("vamsatree.html", tree=family_tree_data, name=session['user']['Alias'], memdata=memdata)


# Find root ancestor
def root_id(member_id):
    row = db.get_member_data(member_id)
    if row:
        if row["Father_ID"] == 0:
            return member_id
        else:
            return root_id(row["Father_ID"])
        flash("Father ID in the system", {member_id})
    else:
        return member_id  # If member data is missing, return the current ID
    
    

# Recursive function to build family tree structure
def build_family_tree(member_id, count, colors):
    row = db.get_member_data(member_id)
    if not row:
        return None

    member_data = { "name": row["Alias"], "color": colors[count],
        "spouse": None, "children": [] }

    if row["Spouse_ID"]:
        spouse_row = db.get_member_data(row["Spouse_ID"])
        if spouse_row:
            member_data["spouse"] = spouse_row["Alias"]

    children = db.get_all_children(member_id)

    if children:
        count += 1
        for child in children:
            child_data = build_family_tree(child["MEMBER_ID"], count, colors)
            if child_data:
                member_data["children"].append(child_data)

    return member_data
