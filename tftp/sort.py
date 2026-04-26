input_file = "REFERENCE-LIST.txt"
output_file = "no-display-name.txt"

with open(input_file, "r") as infile, open(output_file, "w") as outfile:
    for line in infile:
        parts = line.split()
        if len(parts) >= 3:
            description = parts[2]
            if description.upper() == "N/A":
                outfile.write(line)

print(f"Lines with Description = N/A have been saved to {output_file}")