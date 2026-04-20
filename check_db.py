import database
conn = database.get_connection()
cursor = conn.cursor()
cursor.execute('PRAGMA table_info(scores)')
columns = [row[1] for row in cursor.fetchall()]
print("Scores Table Columns:", columns)

# Check if new columns exist
expected = ["cv_match", "north_star_alignment", "compensation", "cultural_signals", "red_flags", "archetype", "legitimacy", "gap_analysis", "personalization_plan", "interview_prep"]
missing = [col for col in expected if col not in columns]
print("Missing Columns:", missing)

if missing:
    print("MIGRATION NEEDED")
else:
    print("SCHEMA IS UP TO DATE")
