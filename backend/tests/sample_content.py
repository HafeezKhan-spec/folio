"""A fictional resume used by the API tests."""

SAMPLE = {
    "contact": {
        "name": "Alex Morgan",
        "headline": "Software engineer",
        "email": "alex@example.com",
        "phone": "+15125550100",
        "location": "Austin, TX",
        "website": "https://example.com",
        "linkedin": "alex-morgan",
        "github": "alex-morgan",
    },
    "summary": "Builds calm software.",
    "experience": [
        {
            "company": "Northwind",
            "position": "Engineer",
            "location": "Austin, TX",
            "start_date": "2022-01",
            "end_date": "present",
            "highlights": ["Shipped the billing page"],
        }
    ],
    "education": [
        {
            "institution": "State University",
            "degree": "BS",
            "area": "Computer Science",
            "location": "Austin, TX",
            "start_date": "2018-09",
            "end_date": "2022-05",
            "highlights": [],
        }
    ],
    "skills": [{"label": "Languages", "details": "Python, TypeScript"}],
    "projects": [
        {
            "name": "Studio",
            "url": "",
            "location": "",
            "start_date": "",
            "end_date": "",
            "summary": "A local resume studio",
            "highlights": ["Exports a single-column PDF"],
        }
    ],
}
