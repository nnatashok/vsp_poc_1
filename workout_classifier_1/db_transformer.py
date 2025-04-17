import json


def transform_to_db_structure(analysis):
    """
    Transform the workout analysis into a database-friendly structure.
    This version excludes explanation columns.

    Args:
        analysis (dict): The combined analysis from the workout classifier

    Returns:
        dict: Transformed data ready for database storage
    """
    # Extract duration and convert to rounded minutes
    duration_str = analysis.get("duration", "0:00")
    minutes = extract_minutes_from_duration(duration_str)

    db_structure = {
        "video_id": analysis.get("video_id", ""),
        "video_url": analysis.get("video_url", ""),
        "video_title": analysis.get("video_title", ""),
        "channel_title": analysis.get("channel_title", ""),
        "duration": analysis.get("duration", ""),
        "duration_minutes": minutes
    }

    # Process category data
    if "category" in analysis and "categories" in analysis["category"]:
        db_structure.update(extract_category_info(analysis["category"]["categories"]))
        # Explanation column removed
    else:
        db_structure.update({
            "category": None,
            "subcategory": None,
            "secondary_category": None,
            "secondary_subcategory": None
        })

    # Process fitness level data
    if "fitness_level" in analysis and "requiredFitnessLevel" in analysis["fitness_level"]:
        db_structure.update(extract_fitness_level_info(analysis["fitness_level"]["requiredFitnessLevel"]))

        # Extract technique difficulty levels
        if "techniqueDifficulty" in analysis["fitness_level"]:
            technique_levels = extract_difficulty_levels(analysis["fitness_level"]["techniqueDifficulty"])
            db_structure.update({
                "primary_technique_difficulty": technique_levels.get("primary_level"),
                "secondary_technique_difficulty": technique_levels.get("secondary_level"),
                "tertiary_technique_difficulty": technique_levels.get("tertiary_level")
            })

        # Extract effort difficulty levels
        if "effortDifficulty" in analysis["fitness_level"]:
            effort_levels = extract_difficulty_levels(analysis["fitness_level"]["effortDifficulty"])
            db_structure.update({
                "primary_effort_difficulty": effort_levels.get("primary_level"),
                "secondary_effort_difficulty": effort_levels.get("secondary_level"),
                "tertiary_effort_difficulty": effort_levels.get("tertiary_level")
            })

        # Explanation columns removed
    else:
        db_structure.update({
            "fitness_level": None,
            "secondary_fitness_level": None,
            "tertiary_fitness_level": None,
            "primary_technique_difficulty": None,
            "secondary_technique_difficulty": None,
            "tertiary_technique_difficulty": None,
            "primary_effort_difficulty": None,
            "secondary_effort_difficulty": None,
            "tertiary_effort_difficulty": None
        })

    # Process equipment data
    if "equipment" in analysis and "requiredEquipment" in analysis["equipment"]:
        db_structure.update(extract_equipment_info(analysis["equipment"]["requiredEquipment"]))
        # Explanation column removed
    else:
        db_structure.update({
            "primary_equipment": None,
            "secondary_equipment": None,
            "tertiary_equipment": None
        })

    # Process spirit data
    if "spirit" in analysis and "spirits" in analysis["spirit"]:
        db_structure.update(extract_spirit_info(analysis["spirit"]["spirits"]))
        # Explanation column removed
    else:
        db_structure.update({
            "primary_spirit": None,
            "secondary_spirit": None
        })

    # Process vibe data
    if "vibe" in analysis and "vibes" in analysis["vibe"]:
        db_structure.update(extract_vibe_info(analysis["vibe"]["vibes"]))
        # Explanation column removed
    else:
        db_structure.update({
            "primary_vibe": None,
            "secondary_vibe": None
        })

    # Add reviewable and review_comment fields
    review_info = check_reviewable(db_structure)
    db_structure.update(review_info)

    return db_structure


def extract_difficulty_levels(difficulty_list):
    """
    Extract primary, secondary, and tertiary difficulty levels from a list of difficulty objects.

    Args:
        difficulty_list (list): List of difficulty objects with level and score

    Returns:
        dict: Primary, secondary, and tertiary difficulty levels
    """
    if not difficulty_list:
        return {
            "primary_level": None,
            "secondary_level": None,
            "tertiary_level": None
        }

    # Sort levels by score in descending order
    sorted_levels = sorted(difficulty_list, key=lambda x: x.get("score", 0), reverse=True)

    # Get highest-scored level
    primary_level = sorted_levels[0]["level"] if sorted_levels else None

    # Check if there's a secondary level with score > 0.5
    secondary_level = None
    if len(sorted_levels) > 1 and sorted_levels[1].get("score", 0) > 0.5:
        secondary_level = sorted_levels[1]["level"]

    # Check if there's a tertiary level with score > 0.5
    tertiary_level = None
    if len(sorted_levels) > 2 and sorted_levels[2].get("score", 0) > 0.5:
        tertiary_level = sorted_levels[2]["level"]

    return {
        "primary_level": primary_level,
        "secondary_level": secondary_level,
        "tertiary_level": tertiary_level
    }


def extract_minutes_from_duration(duration_str):
    """
    Extract and round minutes from a duration string like '1:30:45' or '5:20'.

    Args:
        duration_str (str): Duration string in format HH:MM:SS or MM:SS

    Returns:
        int: Rounded minutes
    """
    try:
        parts = duration_str.split(':')

        if len(parts) == 3:  # HH:MM:SS format
            hours, minutes, seconds = int(parts[0]), int(parts[1]), int(parts[2])
            total_minutes = hours * 60 + minutes + (1 if seconds >= 30 else 0)
        elif len(parts) == 2:  # MM:SS format
            minutes, seconds = int(parts[0]), int(parts[1])
            total_minutes = minutes + (1 if seconds >= 30 else 0)
        else:
            return 0

        return total_minutes
    except (ValueError, IndexError):
        return 0


def check_reviewable(data):
    """
    Check if a workout is reviewable and generate review comments.

    A workout is reviewable if it has at least primary category, subcategory,
    fitness level and vibe set.

    Args:
        data (dict): Workout data

    Returns:
        dict: Reviewable flag and review comments
    """
    missing_tags = []

    # Check required fields
    if not data.get("category"):
        missing_tags.append("No category")
    if not data.get("subcategory"):
        missing_tags.append("No subcategory")
    if not data.get("fitness_level"):
        missing_tags.append("No fitness level")
    if not data.get("primary_vibe"):
        missing_tags.append("No vibe")

    # Determine if reviewable
    reviewable = len(missing_tags) == 0

    return {
        "reviewable": reviewable,
        "review_comment": json.dumps(missing_tags) if missing_tags else ""
    }


def extract_category_info(categories):
    """
    Extract category information and map to high-level categories.

    Args:
        categories (list): List of category objects with name and score

    Returns:
        dict: Category information mapped to database structure
    """
    if not categories:
        return {
            "category": None,
            "subcategory": None,
            "secondary_category": None,
            "secondary_subcategory": None
        }

    # Sort categories by score in descending order
    sorted_categories = sorted(categories, key=lambda x: x.get("score", 0), reverse=True)

    # Get primary subcategory (highest score)
    subcategory = sorted_categories[0]["name"] if sorted_categories else None

    # Check if there's a secondary category with score > 0.5
    secondary_subcategory = None
    if len(sorted_categories) > 1 and sorted_categories[1].get("score", 0) > 0.5:
        secondary_subcategory = sorted_categories[1]["name"]

    # Map subcategories to categories
    category_mapping = {
        "Cardio": ["Elliptical", "HIIT", "Indoor biking", "Mat", "Running", "Treadmill", "Walking"],
        "Flexibility": ["Pilates", "Stretching", "Yoga"],
        "Rest": ["Breathing exercises", "Meditation"],
        "Strength": ["Body weight", "Calisthenics", "Weight workout"]
    }

    # Map primary category
    category = "Other"  # Default to "Other" if not in known categories
    for cat, subcats in category_mapping.items():
        if subcategory in subcats:
            category = cat
            break

    # Map secondary category
    secondary_category = None
    if secondary_subcategory:
        secondary_category = "Other"  # Default to "Other" if not in known categories
        for cat, subcats in category_mapping.items():
            if secondary_subcategory in subcats:
                secondary_category = cat
                break

    return {
        "category": category,
        "subcategory": subcategory,
        "secondary_category": secondary_category,
        "secondary_subcategory": secondary_subcategory
    }


def extract_fitness_level_info(fitness_levels):
    """
    Extract fitness level information and simplify to three categories.
    Also extracts secondary and tertiary fitness levels if their scores are higher than 0.5.

    Args:
        fitness_levels (list): List of fitness level objects with level and score

    Returns:
        dict: Simplified fitness levels for database
    """
    if not fitness_levels:
        return {
            "fitness_level": None,
            "secondary_fitness_level": None,
            "tertiary_fitness_level": None
        }

    # Sort levels by score in descending order
    sorted_levels = sorted(fitness_levels, key=lambda x: x.get("score", 0), reverse=True)

    # Get highest-scored level
    primary_level = sorted_levels[0]["level"] if sorted_levels else None

    # Map to simplified categories (Elite becomes Advanced)
    if primary_level == "Elite":
        primary_level = "Advanced"

    # Check if there's a secondary fitness level with score > 0.5
    secondary_level = None
    if len(sorted_levels) > 1 and sorted_levels[1].get("score", 0) > 0.5:
        secondary_level = sorted_levels[1]["level"]
        # Map secondary level too (Elite becomes Advanced)
        if secondary_level == "Elite":
            secondary_level = "Advanced"

    # Check if there's a tertiary fitness level with score > 0.5
    tertiary_level = None
    if len(sorted_levels) > 2 and sorted_levels[2].get("score", 0) > 0.5:
        tertiary_level = sorted_levels[2]["level"]
        # Map tertiary level too (Elite becomes Advanced)
        if tertiary_level == "Elite":
            tertiary_level = "Advanced"

    return {
        "fitness_level": primary_level,
        "secondary_fitness_level": secondary_level,
        "tertiary_fitness_level": tertiary_level
    }


def extract_equipment_info(equipment_list):
    """
    Extract primary, secondary, and tertiary equipment information.

    Args:
        equipment_list (list): List of equipment objects with equipment name and confidence

    Returns:
        dict: Primary, secondary, and tertiary equipment for database
    """
    if not equipment_list:
        return {
            "primary_equipment": None,
            "secondary_equipment": None,
            "tertiary_equipment": None
        }

    # Filter equipment by confidence threshold (>0.5)
    filtered_equipment = [eq for eq in equipment_list if eq.get("confidence", 0) > 0.5]

    if not filtered_equipment:
        return {
            "primary_equipment": None,
            "secondary_equipment": None,
            "tertiary_equipment": None
        }

    # Sort equipment by confidence score in descending order
    sorted_equipment = sorted(filtered_equipment, key=lambda x: x.get("confidence", 0), reverse=True)

    # Map to simplified equipment categories
    equipment_mapping = {
        "Weights": ["Dumbbells", "Kettlebells", "Medicine balls", "Barbell", "Weight bench"],
        "Rower": ["Rowing machine"],
        "Treadmill": ["Treadmill"],
        "Exercise Bike": ["Exercise bike"]
    }

    # Initialize with 'Other' as default
    primary_equipment = "Other"
    secondary_equipment = None
    tertiary_equipment = None

    if sorted_equipment:
        # Try to map primary equipment
        for equip_category, equip_items in equipment_mapping.items():
            if sorted_equipment[0]["equipment"] in equip_items:
                primary_equipment = equip_category
                break

        # If there's more than one equipment, try to map secondary
        if len(sorted_equipment) > 1:
            secondary_equipment = "Other"
            for equip_category, equip_items in equipment_mapping.items():
                if sorted_equipment[1]["equipment"] in equip_items:
                    secondary_equipment = equip_category
                    break

        # If there's more than two equipment items, try to map tertiary
        if len(sorted_equipment) > 2:
            tertiary_equipment = "Other"
            for equip_category, equip_items in equipment_mapping.items():
                if sorted_equipment[2]["equipment"] in equip_items:
                    tertiary_equipment = equip_category
                    break

    return {
        "primary_equipment": primary_equipment,
        "secondary_equipment": secondary_equipment,
        "tertiary_equipment": tertiary_equipment
    }


def extract_spirit_info(spirits):
    """
    Extract primary and secondary spirit information.

    Args:
        spirits (list): List of spirit objects with name and score

    Returns:
        dict: Primary and secondary spirits for database
    """
    if not spirits:
        return {"primary_spirit": None, "secondary_spirit": None}

    # Sort spirits by score in descending order
    sorted_spirits = sorted(spirits, key=lambda x: x.get("score", 0), reverse=True)

    primary_spirit = sorted_spirits[0]["name"] if sorted_spirits else None

    # Only include secondary spirit if score > 0.5
    secondary_spirit = None
    if len(sorted_spirits) > 1 and sorted_spirits[1].get("score", 0) > 0.5:
        secondary_spirit = sorted_spirits[1]["name"]

    return {
        "primary_spirit": primary_spirit,
        "secondary_spirit": secondary_spirit
    }


def extract_vibe_info(vibes):
    """
    Extract primary and secondary vibe information.

    Args:
        vibes (list): List of vibe objects with name and score

    Returns:
        dict: Primary and secondary vibes for database
    """
    if not vibes:
        return {"primary_vibe": None, "secondary_vibe": None}

    # Sort vibes by score in descending order
    sorted_vibes = sorted(vibes, key=lambda x: x.get("score", 0), reverse=True)

    primary_vibe = sorted_vibes[0]["name"] if sorted_vibes else None

    # Only include secondary vibe if score > 0.5
    secondary_vibe = None
    if len(sorted_vibes) > 1 and sorted_vibes[1].get("score", 0) > 0.5:
        secondary_vibe = sorted_vibes[1]["name"]

    return {
        "primary_vibe": primary_vibe,
        "secondary_vibe": secondary_vibe
    }