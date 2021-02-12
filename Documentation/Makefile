PKGNAME = nvmetcli
INSTALL ?= install
PREFIX := /usr

ASCIIDOC = asciidoc
XMLTO = xmlto --skip-validation

DOCFILES = ${PKGNAME}.txt nvmetproxy.txt
MANPAGES = ${DOCFILES:.txt=.8}
HTMLFILES = ${DOCFILES:.txt=.html}
XMLFILES = ${DOCFILES:.txt=.xml}

%.8: %.xml
	${XMLTO} man $<

%.xml: %.txt
	${ASCIIDOC} -b docbook -d manpage -o $@ $<

%.html: %.txt
	${ASCIIDOC} -a toc -o $@ $<

installdoc: man8

man8: ${MANPAGES}
	${INSTALL} -m 644 $< ${PREFIX}/share/man/man8

uninstalldoc:
	-rm -f ${PREFIX}/share/man/man8/${MANPAGE}

clean:
	-rm -f ${MANPAGES} ${HTMLFILES} ${XMLFILES}
