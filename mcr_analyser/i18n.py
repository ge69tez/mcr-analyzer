# -*- coding: utf-8 -*-
#
# MCR-Analyser
#
# Copyright (C) 2021 Martin Knopp, Technical University of Munich
#
# This program is free software, see the LICENSE file in the root of this
# repository for details

import gettext


def setup_getext(localedir):
    trans = gettext.translation("analyser", localedir, fallback=True)
    trans.install()
