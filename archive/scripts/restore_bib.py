import subprocess

ret = subprocess.run(["git", "show", "HEAD:data/library.bib"], capture_output=True, text=True)

if ret.returncode == 0:
    bib_content = ret.stdout
    with open("data/library.bib.original", "w") as f:
        f.write(bib_content)
    with open("data/library.bib", "w") as f:
        f.write(bib_content)
    print("Successfully restored library.bib from Git HEAD.")
else:
    print("Failed:")
    print(ret.stderr)
