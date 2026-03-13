
import os
import logging
from dotenv import load_dotenv
from database.connection import connect_to_neo4j
from database.operations import normalize_predicate

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


TRIPLES = [

    # Science & Physics
    ("Albert Einstein", "DEVELOPED", "Theory of Relativity"),
    ("Albert Einstein", "BORN_IN", "Ulm, Germany"),
    ("Albert Einstein", "WORKED_AT", "Princeton University"),
    ("Albert Einstein", "RECEIVED", "Nobel Prize in Physics 1921"),
    ("Theory of Relativity", "INCLUDES", "Special Relativity"),
    ("Theory of Relativity", "INCLUDES", "General Relativity"),
    ("Special Relativity", "INTRODUCED_CONCEPT", "E=mc²"),
    ("Isaac Newton", "FORMULATED", "Laws of Motion"),
    ("Isaac Newton", "DISCOVERED", "Law of Universal Gravitation"),
    ("Isaac Newton", "BORN_IN", "Woolsthorpe, England"),
    ("Isaac Newton", "INVENTED", "Calculus"),
    ("Marie Curie", "DISCOVERED", "Polonium"),
    ("Marie Curie", "DISCOVERED", "Radium"),
    ("Marie Curie", "RECEIVED", "Nobel Prize in Physics 1903"),
    ("Marie Curie", "RECEIVED", "Nobel Prize in Chemistry 1911"),
    ("Marie Curie", "BORN_IN", "Warsaw, Poland"),
    ("Quantum Mechanics", "DESCRIBES", "Behavior of subatomic particles"),
    ("Quantum Mechanics", "FOUNDED_BY", "Max Planck"),
    ("Max Planck", "INTRODUCED", "Quantum of Energy"),
    ("Niels Bohr", "PROPOSED", "Bohr Model of Atom"),
    ("Niels Bohr", "BORN_IN", "Copenhagen, Denmark"),
    ("Richard Feynman", "DEVELOPED", "Quantum Electrodynamics"),
    ("Richard Feynman", "RECEIVED", "Nobel Prize in Physics 1965"),
    ("Stephen Hawking", "PROPOSED", "Hawking Radiation"),
    ("Stephen Hawking", "WROTE", "A Brief History of Time"),
    ("Stephen Hawking", "STUDIED", "Black Holes"),
    ("Black Hole", "HAS_PROPERTY", "Event Horizon"),
    ("Black Hole", "HAS_PROPERTY", "Singularity"),
    ("Higgs Boson", "DISCOVERED_AT", "CERN"),
    ("CERN", "LOCATED_IN", "Geneva, Switzerland"),
    ("CERN", "OPERATES", "Large Hadron Collider"),

    # Space & Astronomy
    ("Solar System", "CONTAINS", "Sun"),
    ("Solar System", "CONTAINS", "Mercury"),
    ("Solar System", "CONTAINS", "Venus"),
    ("Solar System", "CONTAINS", "Earth"),
    ("Solar System", "CONTAINS", "Mars"),
    ("Solar System", "CONTAINS", "Jupiter"),
    ("Solar System", "CONTAINS", "Saturn"),
    ("Solar System", "CONTAINS", "Uranus"),
    ("Solar System", "CONTAINS", "Neptune"),
    ("Earth", "HAS_MOON", "Moon"),
    ("Jupiter", "HAS_MOON", "Ganymede"),
    ("Jupiter", "HAS_MOON", "Europa"),
    ("Saturn", "HAS_FEATURE", "Rings"),
    ("Mars", "HAS_FEATURE", "Olympus Mons"),
    ("Milky Way", "IS_TYPE", "Spiral Galaxy"),
    ("Milky Way", "CONTAINS", "Solar System"),
    ("Andromeda", "IS_TYPE", "Spiral Galaxy"),
    ("Andromeda", "IS_NEAREST_GALAXY_TO", "Milky Way"),
    ("NASA", "FOUNDED_IN", "1958"),
    ("NASA", "LOCATED_IN", "Washington D.C."),
    ("Apollo 11", "LANDED_ON", "Moon"),
    ("Apollo 11", "LAUNCHED_IN", "1969"),
    ("Neil Armstrong", "WAS_FIRST_PERSON_ON", "Moon"),
    ("Neil Armstrong", "PART_OF_MISSION", "Apollo 11"),
    ("James Webb Space Telescope", "LAUNCHED_IN", "2021"),
    ("James Webb Space Telescope", "OPERATED_BY", "NASA"),
    ("Hubble Space Telescope", "LAUNCHED_IN", "1990"),
    ("Hubble Space Telescope", "OPERATED_BY", "NASA"),
    ("International Space Station", "ORBITS", "Earth"),
    ("International Space Station", "INHABITED_SINCE", "2000"),

    # Biology & Medicine
    ("DNA", "STANDS_FOR", "Deoxyribonucleic Acid"),
    ("DNA", "DISCOVERED_BY", "Francis Crick and James Watson"),
    ("DNA", "DISCOVERED_IN", "1953"),
    ("Francis Crick", "RECEIVED", "Nobel Prize in Physiology 1962"),
    ("Charles Darwin", "PROPOSED", "Theory of Evolution"),
    ("Charles Darwin", "WROTE", "On the Origin of Species"),
    ("Charles Darwin", "BORN_IN", "Shrewsbury, England"),
    ("Theory of Evolution", "BASED_ON", "Natural Selection"),
    ("Gregor Mendel", "FOUNDED", "Genetics"),
    ("Gregor Mendel", "STUDIED", "Pea Plants"),
    ("Penicillin", "DISCOVERED_BY", "Alexander Fleming"),
    ("Penicillin", "DISCOVERED_IN", "1928"),
    ("Alexander Fleming", "RECEIVED", "Nobel Prize in Physiology 1945"),
    ("Heart", "PUMPS", "Blood"),
    ("Heart", "HAS_CHAMBERS", "Four"),
    ("Brain", "IS_PART_OF", "Nervous System"),
    ("Brain", "CONTROLS", "Body Functions"),
    ("Vaccine", "PREVENTS", "Infectious Diseases"),
    ("Louis Pasteur", "DEVELOPED", "Germ Theory"),
    ("Louis Pasteur", "INVENTED", "Pasteurization"),
    ("Louis Pasteur", "BORN_IN", "Dole, France"),
    ("Human Genome", "CONTAINS", "3 billion base pairs"),
    ("Human Genome Project", "COMPLETED_IN", "2003"),
    ("CRISPR", "USED_FOR", "Gene Editing"),
    ("Insulin", "REGULATES", "Blood Sugar"),
    ("Insulin", "PRODUCED_BY", "Pancreas"),

    # History & Civilizations
    ("Ancient Egypt", "BUILT", "Pyramids"),
    ("Ancient Egypt", "LOCATED_IN", "North Africa"),
    ("Ancient Egypt", "HAD_RULER", "Pharaoh"),
    ("Great Pyramid of Giza", "BUILT_FOR", "Pharaoh Khufu"),
    ("Great Pyramid of Giza", "LOCATED_IN", "Giza, Egypt"),
    ("Roman Empire", "CAPITAL_WAS", "Rome"),
    ("Roman Empire", "FOUNDED_IN", "27 BC"),
    ("Roman Empire", "FELL_IN", "476 AD"),
    ("Julius Caesar", "WAS_LEADER_OF", "Roman Republic"),
    ("Julius Caesar", "ASSASSINATED_IN", "44 BC"),
    ("Cleopatra", "WAS_QUEEN_OF", "Ancient Egypt"),
    ("Cleopatra", "ALLIED_WITH", "Julius Caesar"),
    ("Alexander the Great", "CONQUERED", "Persian Empire"),
    ("Alexander the Great", "FOUNDED", "Alexandria"),
    ("Alexander the Great", "BORN_IN", "Macedonia"),
    ("World War I", "STARTED_IN", "1914"),
    ("World War I", "ENDED_IN", "1918"),
    ("World War II", "STARTED_IN", "1939"),
    ("World War II", "ENDED_IN", "1945"),
    ("World War II", "LED_TO", "United Nations"),
    ("United Nations", "FOUNDED_IN", "1945"),
    ("United Nations", "HEADQUARTERED_IN", "New York City"),
    ("French Revolution", "OCCURRED_IN", "1789"),
    ("French Revolution", "LED_TO", "Abolition of Monarchy in France"),
    ("Napoleon Bonaparte", "BORN_IN", "Corsica"),
    ("Napoleon Bonaparte", "EXILED_TO", "Saint Helena"),
    ("Napoleon Bonaparte", "WON_BATTLE_OF", "Austerlitz"),
    ("Ottoman Empire", "CAPITAL_WAS", "Constantinople"),
    ("Ottoman Empire", "FELL_IN", "1922"),
    ("Mongol Empire", "FOUNDED_BY", "Genghis Khan"),
    ("Mongol Empire", "WAS_LARGEST_CONTIGUOUS", "Land Empire"),

    # Technology & Computing
    ("Internet", "INVENTED_BY", "Tim Berners-Lee"),
    ("World Wide Web", "INVENTED_BY", "Tim Berners-Lee"),
    ("Tim Berners-Lee", "BORN_IN", "London, England"),
    ("Alan Turing", "DEVELOPED", "Turing Machine"),
    ("Alan Turing", "CONSIDERED_FATHER_OF", "Computer Science"),
    ("Alan Turing", "BORN_IN", "London, England"),
    ("Alan Turing", "WORKED_ON", "Enigma Code Breaking"),
    ("Python", "CREATED_BY", "Guido van Rossum"),
    ("Python", "FIRST_RELEASED_IN", "1991"),
    ("Python", "IS_TYPE", "High-Level Programming Language"),
    ("Linux", "CREATED_BY", "Linus Torvalds"),
    ("Linux", "FIRST_RELEASED_IN", "1991"),
    ("Linux", "IS_TYPE", "Open-Source Operating System"),
    ("Google", "FOUNDED_BY", "Larry Page and Sergey Brin"),
    ("Google", "FOUNDED_IN", "1998"),
    ("Google", "HEADQUARTERED_IN", "Mountain View, California"),
    ("Microsoft", "FOUNDED_BY", "Bill Gates and Paul Allen"),
    ("Microsoft", "FOUNDED_IN", "1975"),
    ("Microsoft", "CREATED", "Windows Operating System"),
    ("Apple", "FOUNDED_BY", "Steve Jobs, Steve Wozniak, and Ronald Wayne"),
    ("Apple", "FOUNDED_IN", "1976"),
    ("Apple", "CREATED", "iPhone"),
    ("Steve Jobs", "CO_FOUNDED", "Apple"),
    ("Steve Jobs", "BORN_IN", "San Francisco, California"),
    ("Artificial Intelligence", "SUBFIELD_INCLUDES", "Machine Learning"),
    ("Machine Learning", "SUBFIELD_INCLUDES", "Deep Learning"),
    ("GPT-4", "DEVELOPED_BY", "OpenAI"),
    ("OpenAI", "FOUNDED_IN", "2015"),
    ("OpenAI", "HEADQUARTERED_IN", "San Francisco, California"),
    ("Neo4j", "IS_TYPE", "Graph Database"),
    ("Neo4j", "USES_LANGUAGE", "Cypher"),
    ("LangChain", "USED_FOR", "Building LLM Applications"),
    ("Blockchain", "USED_IN", "Cryptocurrency"),
    ("Bitcoin", "CREATED_BY", "Satoshi Nakamoto"),
    ("Bitcoin", "CREATED_IN", "2009"),

    # Geography & Countries
    ("Egypt", "CAPITAL", "Cairo"),
    ("Egypt", "LOCATED_IN", "North Africa"),
    ("Egypt", "HAS_RIVER", "Nile"),
    ("Egypt", "HAS_MONUMENT", "Great Pyramid of Giza"),
    ("United States", "CAPITAL", "Washington D.C."),
    ("United States", "CURRENCY", "US Dollar"),
    ("United States", "LARGEST_CITY", "New York City"),
    ("China", "CAPITAL", "Beijing"),
    ("China", "MOST_POPULATED_IN", "21st Century"),
    ("China", "HAS_LANDMARK", "Great Wall of China"),
    ("India", "CAPITAL", "New Delhi"),
    ("India", "HAS_MONUMENT", "Taj Mahal"),
    ("India", "HAS_RIVER", "Ganges"),
    ("Brazil", "CAPITAL", "Brasília"),
    ("Brazil", "LARGEST_CITY", "São Paulo"),
    ("Brazil", "HAS_LANDMARK", "Amazon Rainforest"),
    ("France", "CAPITAL", "Paris"),
    ("France", "HAS_LANDMARK", "Eiffel Tower"),
    ("France", "CURRENCY", "Euro"),
    ("Germany", "CAPITAL", "Berlin"),
    ("Japan", "CAPITAL", "Tokyo"),
    ("Japan", "HAS_LANDMARK", "Mount Fuji"),
    ("Russia", "CAPITAL", "Moscow"),
    ("Russia", "LARGEST_COUNTRY_BY", "Land Area"),
    ("Nile", "IS_LONGEST", "River in Africa"),
    ("Amazon", "IS_LARGEST", "River by Volume"),
    ("Sahara", "IS_LARGEST", "Hot Desert in World"),
    ("Mount Everest", "IS_HIGHEST", "Mountain on Earth"),
    ("Mount Everest", "LOCATED_IN", "Nepal and Tibet"),
    ("Mariana Trench", "IS_DEEPEST", "Point in Ocean"),
    ("Mariana Trench", "LOCATED_IN", "Pacific Ocean"),

    # Arts & Literature
    ("William Shakespeare", "WROTE", "Hamlet"),
    ("William Shakespeare", "WROTE", "Romeo and Juliet"),
    ("William Shakespeare", "WROTE", "Macbeth"),
    ("William Shakespeare", "BORN_IN", "Stratford-upon-Avon, England"),
    ("Hamlet", "IS_TYPE", "Tragedy Play"),
    ("Leonardo da Vinci", "PAINTED", "Mona Lisa"),
    ("Leonardo da Vinci", "PAINTED", "The Last Supper"),
    ("Leonardo da Vinci", "BORN_IN", "Vinci, Italy"),
    ("Mona Lisa", "DISPLAYED_IN", "Louvre Museum"),
    ("Louvre Museum", "LOCATED_IN", "Paris, France"),
    ("Michelangelo", "PAINTED", "Sistine Chapel Ceiling"),
    ("Michelangelo", "SCULPTED", "David"),
    ("Michelangelo", "BORN_IN", "Caprese, Italy"),
    ("Beethoven", "COMPOSED", "Symphony No. 9"),
    ("Beethoven", "BORN_IN", "Bonn, Germany"),
    ("Beethoven", "BECAME", "Deaf Later in Life"),
    ("Mozart", "COMPOSED", "The Magic Flute"),
    ("Mozart", "BORN_IN", "Salzburg, Austria"),
    ("J.K. Rowling", "WROTE", "Harry Potter Series"),
    ("Harry Potter Series", "SET_IN", "Hogwarts School"),
    ("Tolstoy", "WROTE", "War and Peace"),
    ("Tolstoy", "BORN_IN", "Tula Oblast, Russia"),
    ("Pablo Picasso", "FOUNDED", "Cubism"),
    ("Pablo Picasso", "PAINTED", "Guernica"),

    # Sports & Athletes
    ("FIFA World Cup", "HELD_EVERY", "4 Years"),
    ("Brazil", "WON_FIFA_WORLD_CUP_TIMES", "5"),
    ("Lionel Messi", "PLAYS_FOR", "Inter Miami"),
    ("Lionel Messi", "BORN_IN", "Rosario, Argentina"),
    ("Lionel Messi", "WON", "FIFA World Cup 2022"),
    ("Cristiano Ronaldo", "BORN_IN", "Funchal, Portugal"),
    ("Cristiano Ronaldo", "PLAYS_FOR", "Al Nassr"),
    ("Olympics", "HELD_EVERY", "4 Years"),
    ("Olympics", "ORIGINATED_IN", "Ancient Greece"),
    ("Usain Bolt", "BORN_IN", "Sherwood Content, Jamaica"),
    ("Usain Bolt", "HOLDS_RECORD_IN", "100m Sprint"),
    ("Usain Bolt", "HOLDS_RECORD_IN", "200m Sprint"),
    ("Michael Jordan", "PLAYED_FOR", "Chicago Bulls"),
    ("Michael Jordan", "WON_NBA_CHAMPIONSHIPS", "6"),
    ("Muhammad Ali", "BORN_IN", "Louisville, Kentucky"),
    ("Muhammad Ali", "WAS_WORLD_CHAMPION_IN", "Heavyweight Boxing"),
    ("Roger Federer", "BORN_IN", "Basel, Switzerland"),
    ("Roger Federer", "WON_GRAND_SLAMS", "20"),
    ("Serena Williams", "BORN_IN", "Saginaw, Michigan"),
    ("Serena Williams", "WON_GRAND_SLAMS", "23"),

    # Economics & Companies
    ("Amazon", "FOUNDED_BY", "Jeff Bezos"),
    ("Amazon", "FOUNDED_IN", "1994"),
    ("Amazon", "HEADQUARTERED_IN", "Seattle, Washington"),
    ("Jeff Bezos", "BORN_IN", "Albuquerque, New Mexico"),
    ("Tesla", "FOUNDED_BY", "Elon Musk and others"),
    ("Tesla", "PRODUCES", "Electric Vehicles"),
    ("Tesla", "HEADQUARTERED_IN", "Austin, Texas"),
    ("Elon Musk", "BORN_IN", "Pretoria, South Africa"),
    ("Elon Musk", "FOUNDED", "SpaceX"),
    ("SpaceX", "ACHIEVED", "First Reusable Rocket Landing"),
    ("SpaceX", "FOUNDED_IN", "2002"),
    ("Meta", "FORMERLY_KNOWN_AS", "Facebook"),
    ("Meta", "FOUNDED_BY", "Mark Zuckerberg"),
    ("Mark Zuckerberg", "BORN_IN", "White Plains, New York"),
    ("Samsung", "HEADQUARTERED_IN", "Seoul, South Korea"),
    ("Samsung", "PRODUCES", "Smartphones"),
    ("Toyota", "HEADQUARTERED_IN", "Toyota City, Japan"),
    ("Toyota", "PRODUCES", "Automobiles"),
    ("Goldman Sachs", "IS_TYPE", "Investment Bank"),
    ("Goldman Sachs", "HEADQUARTERED_IN", "New York City"),

    # Philosophy & Thinkers
    ("Socrates", "TAUGHT", "Plato"),
    ("Socrates", "BORN_IN", "Athens, Greece"),
    ("Socrates", "DEVELOPED", "Socratic Method"),
    ("Plato", "TAUGHT", "Aristotle"),
    ("Plato", "WROTE", "The Republic"),
    ("Plato", "FOUNDED", "The Academy"),
    ("Aristotle", "TAUGHT", "Alexander the Great"),
    ("Aristotle", "WROTE", "Nicomachean Ethics"),
    ("Aristotle", "BORN_IN", "Stagira, Greece"),
    ("Immanuel Kant", "WROTE", "Critique of Pure Reason"),
    ("Immanuel Kant", "BORN_IN", "Königsberg, Prussia"),
    ("Friedrich Nietzsche", "WROTE", "Thus Spoke Zarathustra"),
    ("Friedrich Nietzsche", "COINED_TERM", "Will to Power"),
    ("Karl Marx", "WROTE", "The Communist Manifesto"),
    ("Karl Marx", "CO_AUTHORED_WITH", "Friedrich Engels"),
    ("Karl Marx", "BORN_IN", "Trier, Germany"),
    ("René Descartes", "COINED_PHRASE", "Cogito ergo sum"),
    ("René Descartes", "BORN_IN", "La Haye en Touraine, France"),
    ("René Descartes", "DEVELOPED", "Cartesian Coordinate System"),
    ("Confucius", "BORN_IN", "Qufu, China"),
    ("Confucius", "FOUNDED", "Confucianism"),
    ("John Locke", "INFLUENCED", "American Declaration of Independence"),
    ("Sigmund Freud", "FOUNDED", "Psychoanalysis"),
    ("Sigmund Freud", "BORN_IN", "Freiberg, Moravia"),
    ("Carl Jung", "DEVELOPED", "Analytical Psychology"),
    ("Carl Jung", "STUDIED_UNDER", "Sigmund Freud"),

    # Cinema & Movies
    ("The Godfather", "DIRECTED_BY", "Francis Ford Coppola"),
    ("The Godfather", "RELEASED_IN", "1972"),
    ("Francis Ford Coppola", "BORN_IN", "Detroit, Michigan"),
    ("The Dark Knight", "DIRECTED_BY", "Christopher Nolan"),
    ("The Dark Knight", "FEATURES_CHARACTER", "Batman"),
    ("Christopher Nolan", "DIRECTED", "Inception"),
    ("Pulp Fiction", "DIRECTED_BY", "Quentin Tarantino"),
    ("Quentin Tarantino", "BORN_IN", "Knoxville, Tennessee"),
    ("Avatar", "DIRECTED_BY", "James Cameron"),
    ("Avatar", "RELEASED_IN", "2009"),
    ("Schindler's List", "DIRECTED_BY", "Steven Spielberg"),
    ("Steven Spielberg", "DIRECTED", "Jurassic Park"),
    ("Forrest Gump", "DIRECTED_BY", "Robert Zemeckis"),
    ("Forrest Gump", "RELEASED_IN", "1994"),
    ("Citizen Kane", "DIRECTED_BY", "Orson Welles"),
    ("Citizen Kane", "RELEASED_IN", "1941"),

    # Chemistry & Elements
    ("Hydrogen", "HAS_SYMBOL", "H"),
    ("Hydrogen", "HAS_ATOMIC_NUMBER", "1"),
    ("Oxygen", "HAS_SYMBOL", "O"),
    ("Oxygen", "HAS_ATOMIC_NUMBER", "8"),
    ("Gold", "HAS_SYMBOL", "Au"),
    ("Gold", "HAS_ATOMIC_NUMBER", "79"),
    ("Carbon", "IS_ESSENTIAL_FOR", "Life"),
    ("Carbon", "HAS_ATOMIC_NUMBER", "6"),
    ("Silicon", "USED_IN", "Semiconductors"),
    ("Helium", "IS_TYPE", "Noble Gas"),
    ("Dmitri Mendeleev", "CREATED", "Periodic Table"),

    # Mythology & Folklore
    ("Zeus", "IS_KING_OF", "Greek Gods"),
    ("Zeus", "RULES_FROM", "Mount Olympus"),
    ("Poseidon", "IS_GOD_OF", "Sea"),
    ("Hades", "IS_GOD_OF", "Underworld"),
    ("Odin", "IS_KING_OF", "Norse Gods"),
    ("Odin", "LIVES_IN", "Valhalla"),
    ("Thor", "IS_GOD_OF", "Thunder"),
    ("Thor", "WIELDS", "Mjolnir"),
    ("Ra", "IS_GOD_OF", "Sun"),
    ("Ra", "PART_OF", "Egyptian Mythology"),
    ("Anubis", "IS_GOD_OF", "Mummification"),

    # Music & Composers
    ("Johann Sebastian Bach", "COMPOSED", "Goldberg Variations"),
    ("Johann Sebastian Bach", "BORN_IN", "Eisenach, Germany"),
    ("Frederic Chopin", "BORN_IN", "Zelazowa Wola, Poland"),
    ("Frederic Chopin", "KNOWN_FOR", "Piano Music"),
    ("Pyotr Ilyich Tchaikovsky", "COMPOSED", "The Nutcracker"),
    ("Pyotr Ilyich Tchaikovsky", "BORN_IN", "Votkinsk, Russia"),
    ("The Beatles", "MEMBERS_INCLUDE", "John Lennon"),
    ("The Beatles", "MEMBERS_INCLUDE", "Paul McCartney"),
    ("The Beatles", "MEMBERS_INCLUDE", "George Harrison"),
    ("The Beatles", "MEMBERS_INCLUDE", "Ringo Starr"),
    ("Freddie Mercury", "WAS_SINGER_OF", "Queen"),
    ("Elvis Presley", "KNOWN_AS", "King of Rock and Roll"),

    # Inventions & Inventors
    ("Thomas Edison", "INVENTED", "Light Bulb"),
    ("Thomas Edison", "FOUNDED", "General Electric"),
    ("Alexander Graham Bell", "INVENTED", "Telephone"),
    ("Alexander Graham Bell", "BORN_IN", "Edinburgh, Scotland"),
    ("Nikola Tesla", "DEVELOPED", "Alternating Current"),
    ("Nikola Tesla", "BORN_IN", "Smiljan, Croatia"),
    ("Eli Whitney", "INVENTED", "Cotton Gin"),
    ("Johannes Gutenberg", "INVENTED", "Printing Press"),
    ("James Watt", "IMPROVED", "Steam Engine"),
    ("Guglielmo Marconi", "INVENTED", "Radio"),

    # Landmarks & Architecture
    ("Eiffel Tower", "DESIGNED_BY", "Gustave Eiffel"),
    ("Eiffel Tower", "LOCATED_IN", "Paris, France"),
    ("Statue of Liberty", "LOCATED_IN", "New York City"),
    ("Statue of Liberty", "GIFT_FROM", "France"),
    ("Great Wall of China", "BUILT_TO_PROTECT", "China"),
    ("Colosseum", "LOCATED_IN", "Rome, Italy"),
    ("Taj Mahal", "BUILT_BY", "Shah Jahan"),
    ("Taj Mahal", "LOCATED_IN", "Agra, India"),
    ("Burj Khalifa", "IS_TALLEST_BUILDING_IN", "World"),
    ("Burj Khalifa", "LOCATED_IN", "Dubai, UAE"),
    ("Sydney Opera House", "LOCATED_IN", "Sydney, Australia"),

    # Mythology & Folklore (Extra)
    ("Odin", "HAS_SON", "Thor"),
    ("Odin", "HAS_SON", "Baldur"),
    ("Frigg", "IS_WIFE_OF", "Odin"),
    ("Valkyrie", "CHOOSES_WHO_DIE_IN", "Battle"),
    ("Fenrir", "IS_CHILD_OF", "Loki"),
    ("Loki", "IS_GOD_OF", "Mischief"),
    ("Freya", "IS_GODDESS_OF", "Love"),
    ("Sleipnir", "IS_HORSE_OF", "Odin"),

    # Animals & Biology
    ("Cheetah", "IS_FASTEST_LAND_ANIMAL", "Earth"),
    ("Blue Whale", "IS_LARGEST_ANIMAL", "Earth"),
    ("Ostrich", "IS_LARGEST_BIRD", "Earth"),
    ("Colossal Squid", "HAS_LARGEST_EYE", "Animal Kingdom"),
    ("Honey Badger", "IS_KNOWN_FOR", "Bravery"),
    ("Platypus", "LAYS", "Eggs"),
    ("Koala", "EATS", "Eucalyptus"),
    ("Great White Shark", "LIVES_IN", "Oceans"),

    # Software & Companies
    ("Android", "DEVELOPED_BY", "Google"),
    ("Discord", "USED_FOR", "Community Chat"),
    ("Slack", "USED_FOR", "Workplace Communication"),
    ("Adobe", "CREATED", "Photoshop"),
    ("Autodesk", "CREATED", "AutoCAD"),
    ("Intel", "MANUFACTURES", "Microprocessors"),
    ("Nvidia", "MANUFACTURES", "GPUs"),

    # Mathematics
    ("Pythagoras", "DEVELOPED", "Pythagorean Theorem"),
    ("Archimedes", "DISCOVERED", "Principle of Buoyancy"),
    ("Euclid", "KNOWN_AS", "Father of Geometry"),
    ("Fibonacci", "CREATED", "Fibonacci Sequence"),
    ("Euler", "DISCOVERED", "Euler's Number e"),
]



def seed(graph):
    logger.info("Starting seed — %d triples to insert...", len(TRIPLES))
    success, failed = 0, 0

    with graph.session() as session:
        for subj, pred_raw, obj in TRIPLES:
            pred = normalize_predicate(pred_raw)
            cypher = f"""
            MERGE (s:Entity {{name: $subj}})
            MERGE (o:Entity {{name: $obj}})
            MERGE (s)-[r:{pred}]->(o)
            SET r.seeded = true, r.updated = datetime()
            RETURN 1
            """
            try:
                session.run(cypher, subj=subj, obj=obj)
                success += 1
            except Exception as e:
                logger.error("Failed: %s -[%s]-> %s | %s", subj, pred, obj, e)
                failed += 1

    logger.info("Done! %d inserted,  %d failed.", success, failed)
    print(f"\n Seeding complete: {success} triples inserted, {failed} failed.\n")


def print_stats(graph):
    # Summary of DB
    with graph.session() as session:
        node_count = session.run("MATCH (n:Entity) RETURN count(n) AS cnt").single()["cnt"]
        rel_count  = session.run("MATCH ()-[r]->() RETURN count(r) AS cnt").single()["cnt"]
        rel_types  = list(session.run("MATCH ()-[r]->() RETURN DISTINCT type(r) AS t ORDER BY t"))

    print(f"   Database Stats:")
    print(f"   Nodes     : {node_count}")
    print(f"   Relations : {rel_count}")
    print(f"   Rel Types : {len(rel_types)}")
    print(f"\n   Relationship types:")
    for row in rel_types:
        print(f"     • {row['t']}")


if __name__ == "__main__":
    load_dotenv()
    graph = connect_to_neo4j()
    if not graph:
        print(" Could not connect to Neo4j. Check your .env file.")
    else:
        seed(graph)
        print_stats(graph)
