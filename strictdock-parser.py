import json
import argparse

def json_to_sdoc(json_data):
    # Carica il JSON
    data = json.loads(json_data)
    
    # Inizia a costruire il contenuto del file .sdoc
    sdoc_content = "[DOCUMENT]\n"
    if "TITLE" in data:
        sdoc_content += f"TITLE: {data['TITLE']}\n"
    
    sdoc_content += "\n[FREETEXT]\nThis requirements specification will illustrate the functionalities of the HTR System of the Isolette Project.\n[/FREETEXT]\n"

    # Aggiungi le sezioni e i requisiti
    if "SECTIONS" in data:
        for section in data["SECTIONS"]:
            sdoc_content += "\n[SECTION]\n"
            if "TITLE" in section:
                sdoc_content += f"TITLE: {section['TITLE']}\n"

            if "FREETEXT" in section:
                sdoc_content += f"\n[FREETEXT]\n{section['FREETEXT']}\n[/FREETEXT]\n"
            
            for requirement in section.get("REQUIREMENTS", []):
                sdoc_content += "\n[REQUIREMENT]\n"
                if "UID" in requirement:
                    sdoc_content += f"UID: {requirement['UID']}\n"
                if "TITLE" in requirement:
                    sdoc_content += f"TITLE: {requirement['TITLE']}\n"
                if "STATEMENT" in requirement:
                    sdoc_content += "STATEMENT: >>>\n"
                    sdoc_content += f"{requirement['STATEMENT']}\n"
                    sdoc_content += "<<<\n"
                if "RATIONALE" in requirement:
                    sdoc_content += "RATIONALE: >>>\n"
                    sdoc_content += f"{requirement['RATIONALE']}\n"
                    sdoc_content += "<<<\n"
                if "RELATIONS" in requirement:
                    sdoc_content += "RELATIONS:\n"
                    for relation in requirement["RELATIONS"]:
                        sdoc_content += f"- TYPE: {relation['TYPE']}\n  VALUE: {relation['VALUE']}\n"
            
            sdoc_content += "\n[/SECTION]\n"

    return sdoc_content

def main():
    parser = argparse.ArgumentParser(description="Convert JSON to SDOC format.")
    parser.add_argument("json_file", help="Path to the input JSON file")
    parser.add_argument("sdoc_file", help="Path to the output SDOC file")

    args = parser.parse_args()

    # Leggi il file JSON
    with open(args.json_file, 'r', encoding='utf-8') as file:
        json_data = file.read()

    # Converti il JSON in formato SDOC
    sdoc_output = json_to_sdoc(json_data)

    # Scrivi l'output nel file SDOC
    with open(args.sdoc_file, 'w', encoding='utf-8') as file:
        file.write(sdoc_output)

if __name__ == "__main__":
    main()
