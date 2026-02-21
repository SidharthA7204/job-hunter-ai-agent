import os
import json
import re
from urllib.parse import urlparse
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

# Fail fast with clearer messages if optional deps are missing
try:
    from serpapi import GoogleSearch
except ImportError as e:
    raise SystemExit("Missing dependency 'serpapi'. Install with: pip install serpapi") from e

try:
    from dotenv import load_dotenv
except ImportError as e:
    raise SystemExit("Missing dependency 'python-dotenv'. Install with: pip install python-dotenv") from e

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
        PageBreak,
    )
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
except ImportError as e:
    raise SystemExit("Missing dependency 'reportlab'. Install with: pip install reportlab") from e

# ---------------------------
# Load environment variables
# ---------------------------
load_dotenv()
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")

# Warn early if required secrets are missing
def ensure_env():
    missing = [name for name, val in {
        "SERPAPI_KEY": SERPAPI_KEY,
        "EMAIL_USER": EMAIL_USER,
        "EMAIL_PASS": EMAIL_PASS,
    }.items() if not val]
    if missing:
        raise SystemExit(
            f"Missing environment variables: {', '.join(missing)}. "
            "Set them in a .env file or your shell before running."
        )

# ---------------------------
# Job Preferences Configuration
# ---------------------------
JOB_PREFERENCES = {
    "job_title": "React Native Developer",
    "location": "Bangalore, Karnataka, India",
    "preferred_locations": ["Bangalore", "Remote", "Mumbai", "Pune"],
    "experience_level": "2-5 years",
    "salary_min": 500000,  # INR per annum
    "salary_max": 1500000,
    "job_type": ["Full-time", "Contract"],
    "required_skills": ["React", "React Native", "JavaScript", "TypeScript"],
    "preferred_skills": ["Java", "Python", "Node.js"],
    "work_mode": ["Remote", "Hybrid", "On-site"],
    "company_size": None,
    "industry": None,
}

# Load preferences from file if exists, otherwise use defaults
PREFERENCES_FILE = "job_preferences.json"
if os.path.exists(PREFERENCES_FILE):
    try:
        with open(PREFERENCES_FILE, "r") as f:
            user_prefs = json.load(f)
            JOB_PREFERENCES.update(user_prefs)
            print("Loaded preferences from job_preferences.json")
    except Exception as e:
        print(f"Could not load preferences file: {e}. Using defaults.")

# ---------------------------
# Helpers
# ---------------------------
def format_currency(amount):
    """Format integer currency (INR) with commas, safe if amount is not int."""
    try:
        return f"₹{int(amount):,}"
    except Exception:
        return str(amount)

# ---------------------------
# Build Search Query from Preferences
# ---------------------------
def build_search_query():
    """Build search query from job preferences"""
    query_parts = [JOB_PREFERENCES.get("job_title", "Developer")]

    if JOB_PREFERENCES.get("location"):
        query_parts.append(JOB_PREFERENCES["location"])

    if JOB_PREFERENCES.get("work_mode") and "Remote" in JOB_PREFERENCES["work_mode"]:
        query_parts.append("remote")

    return " ".join(query_parts)

# ---------------------------
# Filter Jobs Based on Preferences
# ---------------------------
def filter_jobs_by_preferences(jobs):
    """Filter jobs based on user preferences"""
    filtered = []

    for job in jobs:
        score = 0
        reasons = []

        job_location = (job.get("location") or "").lower()
        if any(pref_loc.lower() in job_location for pref_loc in JOB_PREFERENCES.get("preferred_locations", [])):
            score += 3
            reasons.append("Location match")
        elif JOB_PREFERENCES.get("location") and JOB_PREFERENCES["location"].lower() in job_location:
            score += 2

        job_desc = ((job.get("description") or "") + " " + (job.get("title") or "")).lower()
        required_found = sum(1 for skill in JOB_PREFERENCES.get("required_skills", []) if skill.lower() in job_desc)
        if required_found == len(JOB_PREFERENCES.get("required_skills", [])) and required_found > 0:
            score += 5
            reasons.append(f"All required skills match ({required_found})")
        elif required_found > 0:
            score += required_found
            reasons.append(f"Some required skills match ({required_found}/{len(JOB_PREFERENCES.get('required_skills', []))})")

        preferred_found = sum(1 for skill in JOB_PREFERENCES.get("preferred_skills", []) if skill.lower() in job_desc)
        if preferred_found > 0:
            score += preferred_found * 0.5
            reasons.append(f"Preferred skills match ({preferred_found})")

        job_type_str = (job.get("job_type") or "").lower()
        if any(jt.lower() in job_type_str for jt in JOB_PREFERENCES.get("job_type", [])):
            score += 1
            reasons.append("Job type match")

        salary_str = str(job.get("salary", "")).lower()
        if "lakh" in salary_str or "lpa" in salary_str:
            numbers = re.findall(r'\d+', salary_str)
            if numbers:
                try:
                    salary_value = int(numbers[0]) * 100000
                    if JOB_PREFERENCES.get("salary_min") <= salary_value <= JOB_PREFERENCES.get("salary_max", float('inf')):
                        score += 2
                        reasons.append("Salary in range")
                except Exception:
                    pass

        if score >= 3:
            job["match_score"] = score
            job["match_reasons"] = reasons
            filtered.append(job)

    filtered.sort(key=lambda x: x.get("match_score", 0), reverse=True)
    return filtered

# ---------------------------
# Search Jobs (SerpAPI)
# ---------------------------
def search_jobs(query, location=None, num_results=20):
    print(f"Searching: {query}")
    jobs = []
    try:
        params = {
            "engine": "google_jobs",
            "q": query,
            "hl": "en",
            "api_key": SERPAPI_KEY,
        }
        if location:
            params["location"] = location

        search = GoogleSearch(params)
        results = search.get_dict()

        for job in results.get("jobs_results", [])[:num_results]:
            title = job.get("title", "N/A")
            company = job.get("company_name", "N/A")
            location_job = job.get("location", "N/A")

            detected_ext = job.get("detected_extensions", {}) or {}
            salary = detected_ext.get("salary", "Not specified")
            if not salary:
                salary = detected_ext.get("schedule_type", "Not specified")

            apply_options = job.get("apply_options", []) or []
            link = "N/A"
            if apply_options:
                first = apply_options[0]
                link = first.get("link") or first.get("url") or job.get("job_highlights", {}).get("url", "N/A")
            else:
                link = job.get("job_highlights", {}).get("url", "N/A")

            description = job.get("description", "No description available") or "No description available"
            posted_date = detected_ext.get("posted_at", "Not specified")
            schedule_type = detected_ext.get("schedule_type", "Not specified")

            job_highlights = job.get("job_highlights", {}) or {}
            experience = "Not specified"
            if isinstance(job_highlights, dict):
                for key, value in job_highlights.items():
                    if "experience" in key.lower() or "years" in key.lower():
                        experience = str(value) if isinstance(value, (str, int)) else "Not specified"
                        break

            jobs.append({
                "title": title,
                "company": company,
                "location": location_job,
                "salary": salary,
                "link": link,
                "description": description,
                "posted_date": posted_date,
                "job_type": schedule_type,
                "experience": experience,
                "skills": []
            })
    except Exception as e:
        print(f"SerpAPI failed: {e}")

    return jobs

# ---------------------------
# Local Summarizer (no API)
# ---------------------------
def summarize_jobs_locally(jobs):
    if not jobs:
        return "No jobs found to summarize."
    summary_lines = []
    for job in jobs[:5]:
        summary_lines.append(f"{job['title']} at {job['company']} in {job['location']}")
    return "Today's top jobs:\n" + "\n".join(summary_lines)

# ---------------------------
# Extract Skills from Description
# ---------------------------
def extract_skills(description):
    """Extract relevant skills from job description"""
    all_skills = set()
    required = JOB_PREFERENCES.get("required_skills", [])
    preferred = JOB_PREFERENCES.get("preferred_skills", [])

    desc_lower = (description or "").lower()

    for skill in required + preferred:
        if skill.lower() in desc_lower:
            all_skills.add(skill)

    tech_keywords = [
        "react", "angular", "vue", "javascript", "typescript", "python", "java",
        "node.js", "express", "mongodb", "sql", "aws", "docker", "kubernetes",
        "git", "html", "css", "redux", "graphql", "rest api", "microservices"
    ]

    for keyword in tech_keywords:
        if keyword in desc_lower:
            # Title-case node.js specially
            if keyword == "node.js":
                all_skills.add("Node.js")
            else:
                all_skills.add(keyword.title())

    return list(all_skills)[:10]

# ---------------------------
# Generate PDF Report (Card-based Design)
# ---------------------------
def generate_pdf(jobs, summary):
    date_str = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    filename = f"Job_Report_{date_str}.pdf"

    doc = SimpleDocTemplate(filename, pagesize=letter,
                           rightMargin=0.75*inch, leftMargin=0.75*inch,
                           topMargin=0.75*inch, bottomMargin=0.75*inch)

    elements = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=20,
        textColor=colors.HexColor('#1a1a1a'),
        spaceAfter=18,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )

    company_style = ParagraphStyle(
        'CompanyName',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#0066cc'),
        spaceAfter=6,
        fontName='Helvetica-Bold'
    )

    job_title_style = ParagraphStyle(
        'JobTitle',
        parent=styles['Heading2'],
        fontSize=12,
        textColor=colors.HexColor('#333333'),
        spaceAfter=8,
        fontName='Helvetica-Bold'
    )

    normal_style = ParagraphStyle(
        'NormalText',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#333333'),
        spaceAfter=6,
        leading=12
    )

    desc_style = ParagraphStyle(
        'Description',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#555555'),
        spaceAfter=8,
        leading=12,
        alignment=TA_JUSTIFY
    )

    elements.append(Paragraph(f"Job Opportunities Report - {datetime.now().strftime('%B %d, %Y')}", title_style))
    elements.append(Spacer(1, 0.12*inch))

    # Preferences summary (safe formatting)
    salary_min_str = format_currency(JOB_PREFERENCES.get('salary_min', 0))
    salary_max_str = format_currency(JOB_PREFERENCES.get('salary_max', '∞'))
    pref_summary = f"""
    <b>Your Preferences:</b><br/>
    Job Title: {JOB_PREFERENCES.get('job_title', 'Any')}<br/>
    Location: {', '.join(JOB_PREFERENCES.get('preferred_locations', ['Any']))}<br/>
    Experience: {JOB_PREFERENCES.get('experience_level', 'Any')}<br/>
    Salary Range: {salary_min_str} - {salary_max_str}<br/>
    Job Type: {', '.join(JOB_PREFERENCES.get('job_type', ['Any']))}
    """
    elements.append(Paragraph(pref_summary, normal_style))
    elements.append(Spacer(1, 0.18*inch))

    # Table header styles
    table_style = ParagraphStyle(
        'TableText',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.HexColor('#333333'),
        leading=10
    )
    table_header_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.white,
        fontName='Helvetica-Bold',
        leading=11
    )

    # Prepare table data
    table_data = []
    header_row = [
        Paragraph("<b>Job Title</b>", table_header_style),
        Paragraph("<b>Company</b>", table_header_style),
        Paragraph("<b>Location</b>", table_header_style),
        Paragraph("<b>Salary</b>", table_header_style),
        Paragraph("<b>Experience</b>", table_header_style),
        Paragraph("<b>Posted Date</b>", table_header_style),
        Paragraph("<b>Apply Link</b>", table_header_style)
    ]
    table_data.append(header_row)

    for job in jobs[:20]:
        t_raw = job.get('title', '') or ''
        title = (t_raw[:40] + ('...' if len(t_raw) > 40 else ''))
        c_raw = job.get('company', '') or ''
        company = (c_raw[:30] + ('...' if len(c_raw) > 30 else ''))
        l_raw = job.get('location', '') or ''
        location = (l_raw[:25] + ('...' if len(l_raw) > 25 else ''))
        salary = str(job.get('salary', 'Not specified'))[:20]
        experience = str(job.get('experience', 'Not specified'))[:15]
        posted_date = str(job.get('posted_date', 'Not specified'))[:15]

        apply_url = job.get('link', 'N/A') or 'N/A'
        if apply_url != 'N/A' and str(apply_url).startswith('http'):
            try:
                domain = urlparse(apply_url).netloc.replace('www.', '')
                if 'linkedin' in domain.lower():
                    apply_text = "Apply on LinkedIn"
                elif 'indeed' in domain.lower():
                    apply_text = "Apply on Indeed"
                elif 'naukri' in domain.lower():
                    apply_text = "Apply on Naukri"
                else:
                    domain_name = domain.split('.')[0].capitalize() if '.' in domain else 'Apply'
                    apply_text = f"Apply on {domain_name}"
                apply_link_text = f'<a href="{apply_url}"><u>{apply_text}</u></a>'
            except Exception:
                apply_link_text = f'<a href="{apply_url}"><u>Click to Apply</u></a>'
        else:
            apply_link_text = "See listing"

        row = [
            Paragraph(title, table_style),
            Paragraph(company, table_style),
            Paragraph(location, table_style),
            Paragraph(salary, table_style),
            Paragraph(experience, table_style),
            Paragraph(posted_date, table_style),
            Paragraph(apply_link_text, table_style)
        ]
        table_data.append(row)

    col_widths = [1.3*inch, 1.1*inch, 1.0*inch, 1.0*inch, 0.8*inch, 0.8*inch, 1.0*inch]
    summary_table = Table(table_data, colWidths=col_widths, repeatRows=1)
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#343a40')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
    ]))

    elements.append(Paragraph("<b>Job Listings Summary Table</b>", ParagraphStyle(
        'TableTitle',
        parent=styles['Heading2'],
        fontSize=12,
        textColor=colors.HexColor('#1a1a1a'),
        spaceAfter=8,
        fontName='Helvetica-Bold'
    )))
    elements.append(summary_table)
    elements.append(Spacer(1, 0.2*inch))

    # Detailed job cards
    elements.append(Paragraph("<b>Detailed Job Descriptions</b>", ParagraphStyle(
        'SectionTitle',
        parent=styles['Heading2'],
        fontSize=12,
        textColor=colors.HexColor('#1a1a1a'),
        spaceAfter=8,
        fontName='Helvetica-Bold'
    )))
    elements.append(Spacer(1, 0.12*inch))

    for idx, job in enumerate(jobs[:15], 1):
        if idx > 1:
            elements.append(Spacer(1, 0.12*inch))

        job["skills"] = extract_skills(job.get("description", ""))

        header_data = [
            [Paragraph(f"<b>{job.get('company', '')}</b>", company_style),
             Paragraph(job.get('location', ''), normal_style)]
        ]
        header_table = Table(header_data, colWidths=[4*inch, 3*inch])
        header_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8f9fa')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 12),
            ('RIGHTPADDING', (0, 0), (-1, -1), 12),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMBORDER', (0, 0), (-1, -1), 1, colors.HexColor('#dee2e6')),
        ]))
        elements.append(header_table)
        elements.append(Spacer(1, 0.08*inch))

        elements.append(Paragraph(f"<b>{job.get('title', '')}</b>", job_title_style))

        details_text = (
            f"<b>Location:</b> {job.get('location', 'Not specified')} &nbsp;&nbsp;"
            f"<b>Experience:</b> {job.get('experience', 'Not specified')} &nbsp;&nbsp;"
            f"<b>Posted:</b> {job.get('posted_date', 'Not specified')} &nbsp;&nbsp;"
            f"<b>Salary:</b> {job.get('salary', 'Not specified')}"
        )
        elements.append(Paragraph(details_text, normal_style))

        if job.get('job_type') and job['job_type'] != 'Not specified':
            elements.append(Paragraph(f"<b>Job Type:</b> {job['job_type']}", normal_style))

        if job.get('match_score'):
            reasons_text = " • ".join(job.get('match_reasons', []))
            elements.append(Paragraph(f"<i><font color='green'>{reasons_text}</font></i>", normal_style))

        elements.append(Spacer(1, 0.06*inch))

        if job.get('skills'):
            skills_text = " ".join([f"[{skill}]" for skill in job['skills'][:12]])
            elements.append(Paragraph(skills_text, normal_style))
            elements.append(Spacer(1, 0.06*inch))

        desc = job.get('description', 'No description available')
        if len(desc) > 500:
            desc = desc[:500] + "..."
        desc = re.sub(r'<[^>]+>', '', desc)
        elements.append(Paragraph(f"<b>Description:</b><br/>{desc}", desc_style))
        elements.append(Spacer(1, 0.06*inch))

        apply_url = job.get('link', 'N/A') or 'N/A'
        if apply_url != 'N/A' and str(apply_url).startswith('http'):
            try:
                domain = urlparse(apply_url).netloc.replace('www.', '')
                if 'linkedin' in domain.lower():
                    apply_text = "Apply on LinkedIn"
                elif 'indeed' in domain.lower():
                    apply_text = "Apply on Indeed"
                else:
                    domain_name = domain.split('.')[0].capitalize() if '.' in domain else 'Apply'
                    apply_text = f"Apply on {domain_name}"
            except Exception:
                apply_text = "Apply Here"
            apply_link = f'<a href="{apply_url}"><u>{apply_text}</u></a>'
        else:
            apply_link = "See listing for apply details"

        apply_box = Table([[Paragraph(apply_link, ParagraphStyle(
            'ApplyLink',
            parent=normal_style,
            fontSize=10,
            fontName='Helvetica-Bold'
        ))]], colWidths=[7*inch])
        apply_box.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#e6f2ff')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('BORDER', (0, 0), (-1, -1), 1, colors.HexColor('#0066cc')),
        ]))
        elements.append(apply_box)

        elements.append(Spacer(1, 0.06*inch))
        divider = Table([['']], colWidths=[7*inch])
        divider.setStyle(TableStyle([
            ('LINEBELOW', (0, 0), (0, -1), 1, colors.HexColor('#dee2e6')),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        elements.append(divider)

        if idx % 3 == 0 and idx < len(jobs[:15]):
            elements.append(PageBreak())

    doc.build(elements)
    print(f"PDF generated: {filename}")
    return filename

# ---------------------------
# Send Email with PDF
# ---------------------------
def send_email_with_pdf(subject, summary, pdf_path):
    msg = MIMEMultipart()
    msg["From"] = EMAIL_USER
    msg["To"] = EMAIL_USER
    msg["Subject"] = subject
    body_text = f"Hello,\n\nHere's your daily job report:\n\n{summary}\n\nSee attached PDF for full details."
    msg.attach(MIMEText(body_text, "plain"))

    try:
        with open(pdf_path, "rb") as file:
            part = MIMEApplication(file.read(), Name=os.path.basename(pdf_path))
            part['Content-Disposition'] = f'attachment; filename="{os.path.basename(pdf_path)}"'
            msg.attach(part)
    except Exception as e:
        print(f"Failed to open PDF for attachment: {e}")
        return

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASS)
            server.send_message(msg)
            print("Email with PDF sent successfully")
    except Exception as e:
        print("Failed to send email:", e)

# ---------------------------
# Save Preferences Function
# ---------------------------
def save_preferences():
    """Save current preferences to JSON file"""
    try:
        with open(PREFERENCES_FILE, "w") as f:
            json.dump(JOB_PREFERENCES, f, indent=4)
        print(f"Preferences saved to {PREFERENCES_FILE}")
    except Exception as e:
        print(f"Failed to save preferences: {e}")

# ---------------------------
# Main
# ---------------------------
if __name__ == "__main__":
    print("Starting Job Agent...")
    print(f"Using Job Preferences:")
    print(f"  Title: {JOB_PREFERENCES.get('job_title')}")
    print(f"  Locations: {', '.join(JOB_PREFERENCES.get('preferred_locations', []))}")
    print(f"  Experience: {JOB_PREFERENCES.get('experience_level')}")
    print(f"  Skills: {', '.join(JOB_PREFERENCES.get('required_skills', []))}")
    print()

    # Validate required environment before making API calls
    ensure_env()

    query = build_search_query()
    location = JOB_PREFERENCES.get("location")

    jobs = search_jobs(query, location=location, num_results=30)

    if not jobs:
        print("No jobs found. Try adjusting your preferences.")
    else:
        print(f"Found {len(jobs)} jobs before filtering...")
        filtered_jobs = filter_jobs_by_preferences(jobs)
        print(f"{len(filtered_jobs)} jobs matched your preferences.")

        if filtered_jobs:
            summary = summarize_jobs_locally(filtered_jobs)
            pdf_file = generate_pdf(filtered_jobs, summary)
            send_email_with_pdf(f"Your Matched Jobs Report - {datetime.now().strftime('%B %d, %Y')}", summary, pdf_file)
        else:
            print("No jobs matched your preferences. Consider relaxing your criteria.")
