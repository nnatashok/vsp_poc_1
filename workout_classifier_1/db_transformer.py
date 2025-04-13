def transform_to_db_structure(analysis):
    """
    Transform the workout analysis into a database-friendly structure.

    Args:
        analysis (dict): The combined analysis from the workout classifier

    Returns:
        dict: Transformed data ready for database storage
    """
    db_structure = {
        "video_id": analysis.get("video_id", ""),
        "video_url": analysis.get("video_url", ""),
        "video_title": analysis.get("video_title", ""),
        "channel_title": analysis.get("channel_title", ""),
        "duration": analysis.get("duration", "")
    }

    # Process category data
    if "category" in analysis and "categories" in analysis["category"]:
        db_structure.update(extract_category_info(analysis["category"]["categories"]))

    # Process fitness level data
    if "fitness_level" in analysis and "requiredFitnessLevel" in analysis["fitness_level"]:
        db_structure.update(extract_fitness_level_info(analysis["fitness_level"]["requiredFitnessLevel"]))

    # Process equipment data
    if "equipment" in analysis and "requiredEquipment" in analysis["equipment"]:
        db_structure.update(extract_equipment_info(analysis["equipment"]["requiredEquipment"]))

    # Process spirit data
    if "spirit" in analysis and "spirits" in analysis["spirit"]:
        db_structure.update(extract_spirit_info(analysis["spirit"]["spirits"]))

    # Process vibe data
    if "vibe" in analysis and "vibes" in analysis["vibe"]:
        db_structure.update(extract_vibe_info(analysis["vibe"]["vibes"]))

    return db_structure


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
    category = None
    for cat, subcats in category_mapping.items():
        if subcategory in subcats:
            category = cat
            break

    # Map secondary category
    secondary_category = None
    if secondary_subcategory:
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

    Args:
        fitness_levels (list): List of fitness level objects with level and score

    Returns:
        dict: Simplified fitness level for database
    """
    if not fitness_levels:
        return {"fitness_level": None}

    # Sort levels by score in descending order
    sorted_levels = sorted(fitness_levels, key=lambda x: x.get("score", 0), reverse=True)

    # Get highest-scored level
    primary_level = sorted_levels[0]["level"] if sorted_levels else None

    # Map to simplified categories (Elite becomes Advanced)
    if primary_level == "Elite":
        primary_level = "Advanced"

    return {"fitness_level": primary_level}


def extract_equipment_info(equipment_list):
    """
    Extract primary and secondary equipment information.

    Args:
        equipment_list (list): List of equipment objects with equipment name and confidence

    Returns:
        dict: Primary and secondary equipment for database
    """
    if not equipment_list:
        return {"primary_equipment": None, "secondary_equipment": None}

    # Filter equipment by confidence threshold (>0.5)
    filtered_equipment = [eq for eq in equipment_list if eq.get("confidence", 0) > 0.5]

    if not filtered_equipment:
        return {"primary_equipment": None, "secondary_equipment": None}

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

    return {
        "primary_equipment": primary_equipment,
        "secondary_equipment": secondary_equipment
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