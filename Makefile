all:
	pandoc -o code_for_plos.docx -f markdown -t docx --toc --standalone -V fontsize=8pt code_for_plos.md
