# Job Hunter Agent

An AI-powered job finder that searches for jobs based on your preferences and generates a beautiful PDF report.

## Features

✅ **Job Preferences System** - Customize your job search criteria
- Job title, location, experience level
- Salary range
- Required and preferred skills
- Job type (Full-time, Contract, etc.)
- Work mode (Remote, Hybrid, On-site)

✅ **Smart Job Filtering** - Jobs are scored and ranked based on your preferences
✅ **Beautiful PDF Reports** - Card-based design matching popular job sites
✅ **Email Delivery** - Automatically emails you the job report with PDF attachment

## Setup

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Create a `.env` file with your API keys:**
```
SERPAPI_KEY=your_serpapi_key_here
EMAIL_USER=your_email@gmail.com
EMAIL_PASS=your_app_password_here
```

**Note:** For Gmail, you'll need to use an [App Password](https://support.google.com/accounts/answer/185833) instead of your regular password.

3. **Customize your preferences:**

Edit `job_preferences.json` or modify the `JOB_PREFERENCES` dictionary in `job_finder_agent.py`:

```json
{
    "job_title": "React Native Developer",
    "location": "Bangalore, Karnataka, India",
    "preferred_locations": ["Bangalore", "Remote", "Mumbai"],
    "experience_level": "2-5 years",
    "salary_min": 500000,
    "salary_max": 1500000,
    "required_skills": ["React", "JavaScript", "TypeScript"],
    "preferred_skills": ["Node.js", "Python"],
    "job_type": ["Full-time", "Contract"],
    "work_mode": ["Remote", "Hybrid"]
}
```

## Usage

Run the script:
```bash
python job_finder_agent.py
```

The script will:
1. Search for jobs based on your preferences
2. Filter and rank jobs by match score
3. Generate a styled PDF report
4. Email the report to you

## Output

- **PDF Report**: `Job_Report_YYYY-MM-DD_HHMMSS.pdf` with card-based job listings
- **Email**: Sent to your email address with PDF attachment

## Customization

- Edit `job_preferences.json` to change your job search criteria
- The PDF will automatically update based on your preferences
- Adjust scoring thresholds in `filter_jobs_by_preferences()` function


