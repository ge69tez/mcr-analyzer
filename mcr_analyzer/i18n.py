#
# MCR-Analyzer
#
# Copyright (C) 2021 Martin Knopp, Technical University of Munich
#
# This program is free software, see the LICENSE file in the root of this
# repository for details

import gettext


def setup_gettext(localedir):
    trans = gettext.translation("analyzer", localedir, fallback=True)
    trans.install()
