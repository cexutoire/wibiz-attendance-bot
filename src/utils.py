from datetime import datetime

def calculate_hours(time_in_str, time_out_str):
    """
    Calculate hours worked between time-in and time-out
    
    Args:
        time_in_str: "9:00 AM" format
        time_out_str: "5:30 PM" format
    
    Returns:
        float: hours worked (e.g., 8.5)
    """
    try:
        # Parse time strings
        time_in = datetime.strptime(time_in_str.strip(), '%I:%M %p')
        time_out = datetime.strptime(time_out_str.strip(), '%I:%M %p')
        
        # Handle case where time_out is before time_in (crossed midnight)
        if time_out < time_in:
            # Add 24 hours to time_out
            from datetime import timedelta
            time_out = time_out + timedelta(hours=24)
        
        # Calculate difference
        time_diff = time_out - time_in
        hours = time_diff.total_seconds() / 3600
        
        return round(hours, 2)
    
    except Exception as e:
        print(f"❌ Error calculating hours: {e}")
        return 0.0

def extract_tasks(message_content):
    """
    Extract task lines from a message
    
    Args:
        message_content: Full message text
    
    Returns:
        list: List of task strings
    """
    tasks = []
    lines = message_content.split('\n')
    
    # Look for lines starting with bullet points or dashes
    in_tasks_section = False
    for line in lines:
        line = line.strip()
        
        # Check if we've reached the Tasks section
        if line.lower().startswith('task'):
            in_tasks_section = True
            continue
        
        # If we're in tasks section, extract bullet points
        if in_tasks_section and line:
            # Check for bullet points: •, -, *, or numbered lists
            if line.startswith('•') or line.startswith('-') or line.startswith('*'):
                task = line[1:].strip()  # Remove bullet
                if task:
                    tasks.append(task)
            elif line[0].isdigit() and (line[1] == '.' or line[1] == ')'):
                task = line[2:].strip()  # Remove number
                if task:
                    tasks.append(task)
    
    return tasks

def extract_urls(text):
    """
    Extract URLs from text
    
    Args:
        text: String to search for URLs
    
    Returns:
        list: List of URLs found
    """
    import re
    url_pattern = r'https?://[^\s]+'
    urls = re.findall(url_pattern, text)
    return urls

# Test the functions
if __name__ == '__main__':
    # Test hours calculation
    hours = calculate_hours("9:00 AM", "5:30 PM")
    print(f"Hours worked: {hours}")  # Should be 8.5
    
    # Test overnight shift
    hours_overnight = calculate_hours("11:00 PM", "7:00 AM")
    print(f"Overnight hours: {hours_overnight}")  # Should be 8.0
    
    # Test task extraction
    test_message = """
Name: Test User
Date: 17 Feb 2026
Time In: 9:00 AM
Time Out: 5:00 PM

Tasks:
- Created attendance bot
- Fixed database issues
📎 Link: https://github.com/test
- Tested the system
"""
    
    tasks = extract_tasks(test_message)
    print(f"\nExtracted tasks: {tasks}")
    
    urls = extract_urls(test_message)
    print(f"Found URLs: {urls}")