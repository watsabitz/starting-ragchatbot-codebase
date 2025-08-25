#!/usr/bin/env python3
"""
Simple verification script to check that all changes were implemented correctly
"""

import os


def check_file_contains(file_path, expected_content, description):
    """Check if a file contains expected content"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            if expected_content in content:
                print(f"[OK] {description}")
                return True
            else:
                print(f"[MISSING] {description}")
                return False
    except FileNotFoundError:
        print(f"[ERROR] File not found: {file_path}")
        return False


def main():
    print("Verifying clickable links implementation...")
    print("=" * 50)

    all_good = True

    # Check backend changes
    search_tools_path = "backend/search_tools.py"
    all_good &= check_file_contains(
        search_tools_path,
        "lesson_link = self.store.get_lesson_link(course_title, lesson_num)",
        "search_tools.py: Added lesson link retrieval",
    )

    all_good &= check_file_contains(
        search_tools_path,
        '"text": source_text,',
        "search_tools.py: Enhanced source structure with text field",
    )

    all_good &= check_file_contains(
        search_tools_path,
        '"link": lesson_link',
        "search_tools.py: Enhanced source structure with link field",
    )

    # Check app.py changes
    app_path = "backend/app.py"
    all_good &= check_file_contains(
        app_path,
        "sources: List[Dict[str, Any]]",
        "app.py: Updated QueryResponse model for Dict sources",
    )

    # Check frontend changes
    script_path = "frontend/script.js"
    all_good &= check_file_contains(
        script_path, "if (source.link) {", "script.js: Added clickable link logic"
    )

    all_good &= check_file_contains(
        script_path, 'target="_blank"', "script.js: Links open in new tab"
    )

    all_good &= check_file_contains(
        script_path, 'class="source-link"', "script.js: Added CSS class for styling"
    )

    # Check CSS changes
    css_path = "frontend/style.css"
    all_good &= check_file_contains(
        css_path, ".source-link {", "style.css: Added source link styling"
    )

    all_good &= check_file_contains(
        css_path,
        "color: var(--primary-color);",
        "style.css: Source links use primary color",
    )

    print("\n" + "=" * 50)
    if all_good:
        print("SUCCESS: ALL CHANGES VERIFIED!")
        print("\nImplementation Summary:")
        print(
            "1. Backend: search_tools.py now retrieves lesson links from vector store"
        )
        print("2. Backend: app.py updated to pass Dict sources to frontend")
        print("3. Frontend: script.js renders clickable links that open in new tabs")
        print("4. Frontend: style.css provides proper styling for source links")
        print("\nSource citations are now clickable links to lesson videos!")
    else:
        print("ERROR: Some changes are missing or incorrect")
        print("Please review the implementation")


if __name__ == "__main__":
    main()
