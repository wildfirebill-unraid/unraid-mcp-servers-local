import json
from typing import Any
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio

SPDX_LICENSES = {
    "MIT": {
        "name": "MIT License",
        "osi_approved": True,
        "fsf_free": True,
        "deprecated": False,
        "permissions": ["commercial-use", "modification", "distribution", "sublicense", "private-use"],
        "conditions": ["include-copyright"],
        "limitations": ["no-liability"],
        "compatibility": {"permissive": ["Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC", "MIT-0", "0BSD", "Unlicense", "CC0-1.0", "BSL-1.0", "Zlib"], "weak-copyleft": ["LGPL-2.1", "LGPL-3.0", "MPL-2.0"], "copyleft": []},
        "text": "MIT License\n\nCopyright (c) [year] [copyright holders]\n\nPermission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the \"Software\"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:\n\nThe above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.\n\nTHE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE."
    },
    "Apache-2.0": {
        "name": "Apache License 2.0",
        "osi_approved": True,
        "fsf_free": True,
        "deprecated": False,
        "permissions": ["commercial-use", "modification", "distribution", "sublicense", "private-use", "patent-use"],
        "conditions": ["include-copyright", "include-license", "state-changes", "notice-file"],
        "limitations": ["no-liability", "no-trademark"],
        "compatibility": {"permissive": ["MIT", "BSD-2-Clause", "BSD-3-Clause", "ISC", "MIT-0", "0BSD", "Unlicense", "CC0-1.0", "Zlib"], "weak-copyleft": ["LGPL-3.0", "MPL-2.0"], "copyleft": ["GPL-3.0"]},
        "text": "Apache License\nVersion 2.0, January 2004\nhttp://www.apache.org/licenses/\n\nTERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION\n\n1. Definitions.\n   \"License\" shall mean the terms and conditions for use, reproduction, and distribution as defined by Sections 1 through 9 of this document.\n   \"Licensor\" shall mean the copyright owner or entity authorized by the copyright owner that is granting the License.\n   \"Legal Entity\" shall mean the union of the acting entity and all other entities that control, are controlled by, or are under common control with that entity.\n   \"You\" (or \"Your\") shall mean an individual or Legal Entity exercising permissions granted by this License.\n   \"Source\" form shall mean the preferred form for making modifications, including but not limited to software source code, documentation source, and configuration files.\n   \"Object\" form shall mean any form resulting from mechanical transformation or translation of a Source form, including but not limited to compiled object code, generated documentation, and conversions to other media types.\n   \"Work\" shall mean the work of authorship, whether in Source or Object form, made available under the License, as indicated by a copyright notice that is included in or attached to the work.\n   \"Derivative Works\" shall mean any work, whether in Source or Object form, that is based on (or derived from) the Work and for which the editorial revisions, annotations, elaborations, or other modifications represent, as a whole, an original work of authorship.\n   \"Contribution\" shall mean any work of authorship, including the original version of the Work and any modifications or additions to that Work or Derivative Works thereof, that is intentionally submitted to Licensor for inclusion in the Work by the copyright owner or by an individual or Legal Entity authorized to submit on behalf of the copyright owner.\n   \"Contributor\" shall mean Licensor and any individual or Legal Entity on behalf of whom a Contribution has been received by Licensor and subsequently incorporated within the Work.\n\n2. Grant of Copyright License. Subject to the terms and conditions of this License, each Contributor hereby grants to You a perpetual, worldwide, non-exclusive, no-charge, royalty-free, irrevocable copyright license to reproduce, prepare Derivative Works of, publicly display, publicly perform, sublicense, and distribute the Work and such Derivative Works in Source or Object form.\n\n3. Grant of Patent License. Subject to the terms and conditions of this License, each Contributor hereby grants to You a perpetual, worldwide, non-exclusive, no-charge, royalty-free, irrevocable (except as stated in this section) patent license to make, have made, use, offer to sell, sell, import, and otherwise transfer the Work, where such license applies only to those patent claims licensable by such Contributor that are necessarily infringed by their Contribution(s) alone or by combination of their Contribution(s) with the Work to which such Contribution(s) was submitted.\n\n4. Redistribution. You may reproduce and distribute copies of the Work or Derivative Works thereof in any medium, with or without modifications, and in Source or Object form, provided that You meet the following conditions:\n   (a) You must give any other recipients of the Work or Derivative Works a copy of this License; and\n   (b) You must cause any modified files to carry prominent notices stating that You changed the files; and\n   (c) You must retain, in the Source form of any Derivative Works that You distribute, all copyright, patent, trademark, and attribution notices from the Source form of the Work, excluding those notices that do not pertain to any part of the Derivative Works; and\n   (d) If the Work includes a \"NOTICE\" text file as part of its distribution, then any Derivative Works that You distribute must include a readable copy of the attribution notices contained within such NOTICE file.\n\n5. Submission of Contributions. Unless You explicitly state otherwise, any Contribution intentionally submitted for inclusion in the Work by You to the Licensor shall be under the terms and conditions of this License, without any additional terms or conditions.\n\n6. Trademarks. This License does not grant permission to use the trade names, trademarks, service marks, or product names of the Licensor, except as required for reasonable and customary use in describing the origin of the Work.\n\n7. Disclaimer of Warranty. Unless required by applicable law or agreed to in writing, Licensor provides the Work (and each Contributor provides its Contributions) on an \"AS IS\" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND.\n\n8. Limitation of Liability. In no event and under no legal theory shall any Contributor be liable to You for damages.\n\n9. Accepting Warranty or Additional Liability. While redistributing the Work or Derivative Works thereof, You may choose to offer, and charge a fee for, acceptance of support, warranty, indemnity, or other liability obligations."
    },
    "GPL-2.0": {
        "name": "GNU General Public License v2.0",
        "osi_approved": True,
        "fsf_free": True,
        "deprecated": False,
        "permissions": ["commercial-use", "modification", "distribution", "private-use"],
        "conditions": ["include-copyright", "include-license", "state-changes", "disclose-source", "same-license"],
        "limitations": ["no-liability"],
        "compatibility": {"permissive": [], "weak-copyleft": [], "copyleft": ["GPL-3.0"]},
        "text": "GNU GENERAL PUBLIC LICENSE\nVersion 2, June 1991\n\nCopyright (C) 1989, 1991 Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA\n\nEveryone is permitted to copy and distribute verbatim copies of this license document, but changing it is not allowed.\n\nPreamble\nThe licenses for most software are designed to take away your freedom to share and change it. By contrast, the GNU General Public License is intended to guarantee your freedom to share and change free software--to make sure the software is free for all its users.\n\nTERMS AND CONDITIONS FOR COPYING, DISTRIBUTION AND MODIFICATION\n\n0. This License applies to any program or other work which contains a notice placed by the copyright holder saying it may be distributed under the terms of this General Public License.\n\n1. You may copy and distribute verbatim copies of the Program's source code as you receive it, in any medium, provided that you conspicuously and appropriately publish on each copy an appropriate copyright notice and disclaimer of warranty; keep intact all the notices that refer to this License and to the absence of any warranty; and give any other recipients of the Program a copy of this License along with the Program.\n\n2. You may modify your copy or copies of the Program or any portion of it, thus forming a work based on the Program, and copy and distribute such modifications or work under the terms of Section 1 above, provided that you also meet all of these conditions:\n   a) You must cause the modified files to carry prominent notices stating that you changed the files and the date of any change.\n   b) You must cause any work that you distribute or publish, that in whole or in part contains or is derived from the Program or any part thereof, to be licensed as a whole at no charge to all third parties under the terms of this License.\n\n3. You may copy and distribute the Program (or a work based on it, under Section 2) in object code or executable form under the terms of Sections 1 and 2 above provided that you also do one of the following:\n   a) Accompany it with the complete corresponding machine-readable source code.\n   b) Accompany it with a written offer, valid for at least three years, to give any third party a copy of the corresponding source code.\n\nNO WARRANTY\n11. BECAUSE THE PROGRAM IS LICENSED FREE OF CHARGE, THERE IS NO WARRANTY FOR THE PROGRAM, TO THE EXTENT PERMITTED BY APPLICABLE LAW."
    },
    "GPL-3.0": {
        "name": "GNU General Public License v3.0",
        "osi_approved": True,
        "fsf_free": True,
        "deprecated": False,
        "permissions": ["commercial-use", "modification", "distribution", "private-use", "patent-use"],
        "conditions": ["include-copyright", "include-license", "state-changes", "disclose-source", "same-license", "install-information"],
        "limitations": ["no-liability"],
        "compatibility": {"permissive": ["Apache-2.0"], "weak-copyleft": [], "copyleft": ["GPL-2.0", "AGPL-3.0"]},
        "text": "GNU GENERAL PUBLIC LICENSE\nVersion 3, 29 June 2007\n\nCopyright (C) 2007 Free Software Foundation, Inc. <https://fsf.org/>\n\nEveryone is permitted to copy and distribute verbatim copies of this license document, but changing it is not allowed.\n\nPreamble\nThe GNU General Public License is a free, copyleft license for software and other kinds of works.\n\nTERMS AND CONDITIONS\n0. Definitions.\n1. Source Code.\n2. Basic Permissions.\n3. Protecting Users' Legal Rights From Anti-Circumvention Law.\n4. Conveying Verbatim Copies.\n5. Conveying Modified Source Versions.\n6. Conveying Non-Source Forms.\n7. Additional Terms.\n8. Termination.\n9. Acceptance Not Required for Having Copies.\n10. Automatic Licensing of Downstream Recipients.\n11. Patents.\n12. No Surrender of Others' Freedom.\n13. Use with the GNU Affero General Public License.\n14. Revised Versions of this License.\n15. Disclaimer of Warranty.\n16. Limitation of Liability.\n17. Interpretation of Sections 15 and 16.\n\nSee https://www.gnu.org/licenses/gpl-3.0.txt for full text."
    },
    "LGPL-2.1": {
        "name": "GNU Lesser General Public License v2.1",
        "osi_approved": True,
        "fsf_free": True,
        "deprecated": False,
        "permissions": ["commercial-use", "modification", "distribution", "private-use", "sublicense"],
        "conditions": ["include-copyright", "include-license", "state-changes", "disclose-source"],
        "limitations": ["no-liability"],
        "compatibility": {"permissive": ["MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC"], "weak-copyleft": ["LGPL-3.0"], "copyleft": ["GPL-2.0", "GPL-3.0"]},
        "text": "GNU LESSER GENERAL PUBLIC LICENSE\nVersion 2.1, February 1999\n\nCopyright (C) 1991, 1999 Free Software Foundation, Inc. 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA\n\nEveryone is permitted to copy and distribute verbatim copies of this license document, but changing it is not allowed.\n\n[This is the first released version of the Lesser GPL. It also counts as the successor of the GNU Library Public License, version 2, hence the version number 2.1.]\n\nPreamble\nThe licenses for most software are designed to take away your freedom to share and change it. By contrast, the GNU General Public Licenses are intended to guarantee your freedom to share and change free software.\n\nTERMS AND CONDITIONS FOR COPYING, DISTRIBUTION AND MODIFICATION\n0. This License Agreement applies to any software library or other program which contains a notice placed by the copyright holder.\n1. You may copy and distribute verbatim copies of the Library's complete source code.\n2. You may modify your copy or copies of the Library.\n3. You may opt to apply the terms of the ordinary GNU General Public License.\n4. You may copy and distribute the Library.\n5. A program that contains no derivative of any portion of the Library, but is designed to work with the Library by being compiled or linked with it, is called a \"Work that uses the Library\".\n6. As an exception to the Sections above, you may also combine or link a \"Work that uses the Library\" with the Library.\nNO WARRANTY\n15. BECAUSE THE LIBRARY IS LICENSED FREE OF CHARGE, THERE IS NO WARRANTY FOR THE LIBRARY."
    },
    "LGPL-3.0": {
        "name": "GNU Lesser General Public License v3.0",
        "osi_approved": True,
        "fsf_free": True,
        "deprecated": False,
        "permissions": ["commercial-use", "modification", "distribution", "private-use", "sublicense", "patent-use"],
        "conditions": ["include-copyright", "include-license", "state-changes", "disclose-source"],
        "limitations": ["no-liability"],
        "compatibility": {"permissive": ["MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC"], "weak-copyleft": ["LGPL-2.1", "MPL-2.0"], "copyleft": ["GPL-2.0", "GPL-3.0", "AGPL-3.0"]},
        "text": "GNU LESSER GENERAL PUBLIC LICENSE\nVersion 3, 29 June 2007\n\nCopyright (C) 2007 Free Software Foundation, Inc. <https://fsf.org/>\n\nEveryone is permitted to copy and distribute verbatim copies of this license document, but changing it is not allowed.\n\nThis version of the GNU Lesser General Public License incorporates the terms and conditions of version 3 of the GNU General Public License, supplemented by the additional permissions listed below.\n\n0. Additional Definitions.\n1. Exception to Section 3 of the GNU GPL.\n2. Conveying Modified Versions.\n3. Object Code Incorporating Material from Library Header Files.\n4. Combined Works.\n5. Combined Libraries.\n6. Revised Versions of the GNU Lesser General Public License.\n\nSee https://www.gnu.org/licenses/lgpl-3.0.txt for full text."
    },
    "BSD-2-Clause": {
        "name": "BSD 2-Clause \"Simplified\" License",
        "osi_approved": True,
        "fsf_free": True,
        "deprecated": False,
        "permissions": ["commercial-use", "modification", "distribution", "private-use"],
        "conditions": ["include-copyright"],
        "limitations": ["no-liability"],
        "compatibility": {"permissive": ["MIT", "Apache-2.0", "BSD-3-Clause", "ISC", "MIT-0", "0BSD", "Unlicense", "CC0-1.0", "Zlib"], "weak-copyleft": ["LGPL-2.1", "LGPL-3.0", "MPL-2.0"], "copyleft": ["GPL-2.0", "GPL-3.0"]},
        "text": "BSD 2-Clause License\n\nCopyright (c) [year], [copyright holder]\n\nRedistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:\n\n1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.\n\n2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.\n\nTHIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS \"AS IS\" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES."
    },
    "BSD-3-Clause": {
        "name": "BSD 3-Clause \"New\" or \"Revised\" License",
        "osi_approved": True,
        "fsf_free": True,
        "deprecated": False,
        "permissions": ["commercial-use", "modification", "distribution", "private-use"],
        "conditions": ["include-copyright"],
        "limitations": ["no-liability", "no-trademark"],
        "compatibility": {"permissive": ["MIT", "Apache-2.0", "BSD-2-Clause", "ISC", "MIT-0", "0BSD", "Unlicense", "CC0-1.0", "Zlib"], "weak-copyleft": ["LGPL-2.1", "LGPL-3.0", "MPL-2.0"], "copyleft": ["GPL-2.0", "GPL-3.0"]},
        "text": "BSD 3-Clause License\n\nCopyright (c) [year], [copyright holder]\n\nRedistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:\n\n1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.\n\n2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.\n\n3. Neither the name of the copyright holder nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission.\n\nTHIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS \"AS IS\" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES."
    },
    "MPL-2.0": {
        "name": "Mozilla Public License 2.0",
        "osi_approved": True,
        "fsf_free": True,
        "deprecated": False,
        "permissions": ["commercial-use", "modification", "distribution", "sublicense", "private-use"],
        "conditions": ["include-copyright", "include-license", "disclose-source", "notice-file"],
        "limitations": ["no-liability", "no-trademark"],
        "compatibility": {"permissive": ["MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC", "Zlib"], "weak-copyleft": ["LGPL-2.1", "LGPL-3.0"], "copyleft": ["GPL-2.0", "GPL-3.0", "AGPL-3.0"]},
        "text": "Mozilla Public License\nVersion 2.0\n\n1. Definitions\n2. License Grants\n3. Distribution Obligations\n4. Inability to Comply Due to Statute or Regulation\n5. Termination\n6. Disclaimer of Warranty\n7. Limitation of Liability\n8. Litigation\n9. Miscellaneous\n10. Versions of the License\n\nSee https://www.mozilla.org/en-US/MPL/2.0/ for full text."
    },
    "AGPL-3.0": {
        "name": "GNU Affero General Public License v3.0",
        "osi_approved": True,
        "fsf_free": True,
        "deprecated": False,
        "permissions": ["commercial-use", "modification", "distribution", "private-use", "patent-use"],
        "conditions": ["include-copyright", "include-license", "state-changes", "disclose-source", "same-license", "network-use-disclosure"],
        "limitations": ["no-liability"],
        "compatibility": {"permissive": [], "weak-copyleft": [], "copyleft": ["GPL-3.0"]},
        "text": "GNU AFFERO GENERAL PUBLIC LICENSE\nVersion 3, 19 November 2007\n\nCopyright (C) 2007 Free Software Foundation, Inc. <https://fsf.org/>\n\nEveryone is permitted to copy and distribute verbatim copies of this license document, but changing it is not allowed.\n\nPreamble\nThe GNU Affero General Public License is a free, copyleft license for software and other kinds of works, specifically designed to ensure cooperation with the community in the case of network server software.\n\nTERMS AND CONDITIONS\n0. Definitions.\n1. Source Code.\n2. Basic Permissions.\n3. Protecting Users' Legal Rights From Anti-Circumvention Law.\n4. Conveying Verbatim Copies.\n5. Conveying Modified Source Versions.\n6. Conveying Non-Source Forms.\n7. Additional Terms.\n8. Termination.\n9. Acceptance Not Required for Having Copies.\n10. Automatic Licensing of Downstream Recipients.\n11. Patents.\n12. No Surrender of Others' Freedom.\n13. Remote Network Interaction; Use with the GNU General Public License.\n14. Revised Versions of this License.\n15. Disclaimer of Warranty.\n16. Limitation of Liability.\n\nSee https://www.gnu.org/licenses/agpl-3.0.txt for full text."
    },
    "Unlicense": {
        "name": "The Unlicense",
        "osi_approved": True,
        "fsf_free": True,
        "deprecated": False,
        "permissions": ["commercial-use", "modification", "distribution", "sublicense", "private-use"],
        "conditions": [],
        "limitations": ["no-liability"],
        "compatibility": {"permissive": ["MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC", "MIT-0", "0BSD", "CC0-1.0", "Zlib"], "weak-copyleft": ["LGPL-2.1", "LGPL-3.0", "MPL-2.0"], "copyleft": ["GPL-2.0", "GPL-3.0"]},
        "text": "This is free and unencumbered software released into the public domain.\n\nAnyone is free to copy, modify, publish, use, compile, sell, or distribute this software, either in source code form or as a compiled binary, for any purpose, commercial or non-commercial, and by any means.\n\nIn jurisdictions that recognize copyright laws, the author or authors of this software dedicate any and all copyright interest in the software to the public domain. We make this dedication for the benefit of the public at large and to the detriment of our heirs and successors. We intend this dedication to be an overt act of relinquishment in perpetuity of all present and future rights to this software under copyright law.\n\nTHE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE."
    },
    "CC0-1.0": {
        "name": "Creative Commons Zero v1.0 Universal",
        "osi_approved": False,
        "fsf_free": True,
        "deprecated": False,
        "permissions": ["commercial-use", "modification", "distribution", "sublicense", "private-use"],
        "conditions": [],
        "limitations": ["no-liability", "no-trademark"],
        "compatibility": {"permissive": ["MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC", "MIT-0", "0BSD", "Unlicense", "Zlib"], "weak-copyleft": ["LGPL-2.1", "LGPL-3.0", "MPL-2.0"], "copyleft": ["GPL-2.0", "GPL-3.0"]},
        "text": "Creative Commons Legal Code\n\nCC0 1.0 Universal\n\nCREATIVE COMMONS CORPORATION IS NOT A LAW FIRM AND DOES NOT PROVIDE LEGAL SERVICES. DISTRIBUTION OF THIS DOCUMENT DOES NOT CREATE AN ATTORNEY-CLIENT RELATIONSHIP. CREATIVE COMMONS PROVIDES THIS INFORMATION ON AN \"AS-IS\" BASIS. CREATIVE COMMONS MAKES NO WARRANTIES REGARDING THE USE OF THIS DOCUMENT OR THE INFORMATION OR WORKS PROVIDED HEREUNDER.\n\nStatement of Purpose\nThe laws of most jurisdictions throughout the world automatically confer exclusive Copyright and Related Rights (defined below) upon the creator and subsequent owner(s) (each and all, an \"owner\") of an original work of authorship and/or a database (each, a \"Work\").\n\nCertain owners wish to permanently relinquish those rights to a Work for the purpose of contributing to a commons of creative, cultural and scientific works (\"Commons\") that the public can reliably and without fear of later claims of infringement build upon, modify, incorporate in other works, reuse and redistribute as freely as possible in any form whatsoever and for any purposes, including without limitation commercial purposes. These owners may contribute to the Commons to promote the ideal of a free culture and the further production of creative, cultural and scientific works, or to gain reputation or greater distribution for their Work in part through the use and efforts of others.\n\nFor these and/or other purposes and motivations, and without any expectation of additional consideration or compensation, the person associating CC0 with a Work (the \"Affirmer\"), to the extent that he or she is an owner of Copyright and Related Rights in the Work, voluntarily elects to apply CC0 to the Work and publicly distribute the Work under its terms, with knowledge of his or her Copyright and Related Rights in the Work and the meaning and intended legal effect of CC0 on those rights.\n\n1. Copyright and Related Rights. A Work made available under CC0 may be protected by copyright and related or neighboring rights.\n\n2. Waiver. To the greatest extent permitted by, but not in contravention of, applicable law, Affirmer hereby overtly, fully, permanently, irrevocably and unconditionally waives, abandons, and surrenders all of Affirmer's Copyright and Related Rights and associated claims and causes of action.\n\n3. Public License Fallback. Should any part of the Waiver for any reason be judged legally invalid or ineffective under applicable law, then the Waiver shall be preserved to the maximum extent permitted taking into account Affirmer's express Statement of Purpose.\n\n4. Limitations and Disclaimers."
    },
    "ISC": {
        "name": "ISC License",
        "osi_approved": True,
        "fsf_free": True,
        "deprecated": False,
        "permissions": ["commercial-use", "modification", "distribution", "private-use"],
        "conditions": ["include-copyright"],
        "limitations": ["no-liability"],
        "compatibility": {"permissive": ["MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "MIT-0", "0BSD", "Unlicense", "CC0-1.0", "Zlib"], "weak-copyleft": ["LGPL-2.1", "LGPL-3.0", "MPL-2.0"], "copyleft": ["GPL-2.0", "GPL-3.0"]},
        "text": "ISC License\n\nCopyright (c) [year], [copyright holder]\n\nPermission to use, copy, modify, and/or distribute this software for any purpose with or without fee is hereby granted, provided that the above copyright notice and this permission notice appear in all copies.\n\nTHE SOFTWARE IS PROVIDED \"AS IS\" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE."
    },
    "MIT-0": {
        "name": "MIT No Attribution",
        "osi_approved": True,
        "fsf_free": True,
        "deprecated": False,
        "permissions": ["commercial-use", "modification", "distribution", "sublicense", "private-use"],
        "conditions": [],
        "limitations": ["no-liability"],
        "compatibility": {"permissive": ["MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC", "0BSD", "Unlicense", "CC0-1.0", "Zlib"], "weak-copyleft": ["LGPL-2.1", "LGPL-3.0", "MPL-2.0"], "copyleft": ["GPL-2.0", "GPL-3.0"]},
        "text": "MIT No Attribution\n\nCopyright (c) [year] [copyright holders]\n\nPermission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the \"Software\"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so.\n\nTHE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE."
    },
    "0BSD": {
        "name": "BSD Zero Clause License",
        "osi_approved": True,
        "fsf_free": True,
        "deprecated": False,
        "permissions": ["commercial-use", "modification", "distribution", "sublicense", "private-use"],
        "conditions": [],
        "limitations": ["no-liability"],
        "compatibility": {"permissive": ["MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC", "MIT-0", "Unlicense", "CC0-1.0", "Zlib"], "weak-copyleft": ["LGPL-2.1", "LGPL-3.0", "MPL-2.0"], "copyleft": ["GPL-2.0", "GPL-3.0"]},
        "text": "BSD Zero Clause License\n\nCopyright (c) [year] [copyright holder]\n\nPermission to use, copy, modify, and/or distribute this software for any purpose with or without fee is hereby granted.\n\nTHE SOFTWARE IS PROVIDED \"AS IS\" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE."
    },
    "BSL-1.0": {
        "name": "Boost Software License 1.0",
        "osi_approved": True,
        "fsf_free": True,
        "deprecated": False,
        "permissions": ["commercial-use", "modification", "distribution", "sublicense", "private-use"],
        "conditions": ["include-copyright"],
        "limitations": ["no-liability"],
        "compatibility": {"permissive": ["MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC", "MIT-0", "0BSD", "Unlicense", "CC0-1.0", "Zlib"], "weak-copyleft": ["LGPL-2.1", "LGPL-3.0", "MPL-2.0"], "copyleft": ["GPL-2.0", "GPL-3.0"]},
        "text": "Boost Software License - Version 1.0 - August 17th, 2003\n\nPermission is hereby granted, free of charge, to any person or organization obtaining a copy of the software and accompanying documentation covered by this license (the \"Software\") to use, reproduce, display, distribute, execute, and transmit the Software, and to prepare derivative works of the Software, and to permit third-parties to whom the Software is furnished to do so, all subject to the following:\n\nThe copyright notices in the Software and this entire statement, including the above license grant, this restriction and the following disclaimer, must be included in all copies of the Software, in whole or in part, and all derivative works of the Software, unless such copies or derivative works are solely in the form of machine-executable object code generated by a source language processor.\n\nTHE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, TITLE AND NON-INFRINGEMENT. IN NO EVENT SHALL THE COPYRIGHT HOLDERS OR ANYONE DISTRIBUTING THE SOFTWARE BE LIABLE FOR ANY DAMAGES OR OTHER LIABILITY, WHETHER IN CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE."
    },
    "Artistic-2.0": {
        "name": "Artistic License 2.0",
        "osi_approved": True,
        "fsf_free": True,
        "deprecated": False,
        "permissions": ["commercial-use", "modification", "distribution", "sublicense", "private-use"],
        "conditions": ["include-copyright", "include-license", "state-changes"],
        "limitations": ["no-liability"],
        "compatibility": {"permissive": ["MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC"], "weak-copyleft": ["LGPL-2.1", "LGPL-3.0"], "copyleft": []},
        "text": "Artistic License 2.0\n\nCopyright (c) [year] [copyright holder]\n\nEveryone is permitted to copy and distribute verbatim copies of this license document, but changing it is not allowed.\n\nPreamble\nThis license establishes the terms under which a Package may be copied, modified, distributed, and/or redistributed.\n\nDefinitions\n\"Package\" refers to the collection of files distributed by the Copyright Holder.\n\nTerms and Conditions for Use, Copying, Distribution, and Modification\n\n1. You may make and give away verbatim copies of the source form of the Standard Version of this Package without restriction, provided that you duplicate all of the original copyright notices and associated disclaimers.\n\n2. You may apply bug fixes, portability fixes, and other modifications derived from the Public Domain or from the Copyright Holder.\n\n3. You may otherwise modify your copy of this Package in any way, provided that you insert a prominent notice in each changed file stating how and when you changed that file.\n\n4. You may distribute the Standard Version of the Package or modified versions.\n\n5. You may charge a reasonable copying fee for any distribution of this Package.\n\n6. The names of the Copyright Holder may not be used to endorse or promote products derived from this software without specific prior written permission.\n\n7. THIS PACKAGE IS PROVIDED \"AS IS\" AND WITHOUT ANY EXPRESS OR IMPLIED WARRANTIES.\n\nSee https://opensource.org/licenses/Artistic-2.0 for full text."
    },
    "EPL-2.0": {
        "name": "Eclipse Public License 2.0",
        "osi_approved": True,
        "fsf_free": True,
        "deprecated": False,
        "permissions": ["commercial-use", "modification", "distribution", "sublicense", "private-use"],
        "conditions": ["include-copyright", "include-license", "disclose-source"],
        "limitations": ["no-liability"],
        "compatibility": {"permissive": ["MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC"], "weak-copyleft": ["LGPL-2.1", "LGPL-3.0"], "copyleft": ["GPL-2.0", "GPL-3.0"]},
        "text": "Eclipse Public License - v 2.0\n\nTHE ACCOMPANYING PROGRAM IS PROVIDED UNDER THE TERMS OF THIS ECLIPSE PUBLIC LICENSE (\"AGREEMENT\"). ANY USE, REPRODUCTION OR DISTRIBUTION OF THE PROGRAM CONSTITUTES RECIPIENT'S ACCEPTANCE OF THIS AGREEMENT.\n\n1. DEFINITIONS\n\"Contribution\" means:\n  a) in the case of the initial Contributor, the initial content Distributed under this Agreement, and\n  b) in the case of each subsequent Contributor, changes to the Program, as well as additions to the Program, where such changes and/or additions to the Program originate from and are Distributed by that particular Contributor.\n\n2. GRANT OF RIGHTS\n  a) Subject to the terms of this Agreement, each Contributor hereby grants Recipient a non-exclusive, worldwide, royalty-free copyright license to reproduce, prepare derivative works of, publicly display, publicly perform, Distribute and sublicense the Contribution of such Contributor, if any.\n\n3. REQUIREMENTS\nA Contributor may choose to distribute the Program in object code form under its own license agreement.\n\n4. COMMERCIAL DISTRIBUTION\nCommercial distributors of software may accept certain responsibilities with respect to end users.\n\n5. NO WARRANTY\nEXCEPT AS EXPRESSLY SET FORTH IN THIS AGREEMENT, AND TO THE EXTENT PERMITTED BY APPLICABLE LAW, THE PROGRAM IS PROVIDED ON AN \"AS IS\" BASIS.\n\n6. DISCLAIMER OF LIABILITY\nEXCEPT AS EXPRESSLY SET FORTH IN THIS AGREEMENT, AND TO THE EXTENT PERMITTED BY APPLICABLE LAW, NEITHER RECIPIENT NOR ANY CONTRIBUTORS SHALL HAVE ANY LIABILITY.\n\nSee https://www.eclipse.org/legal/epl-2.0/ for full text."
    },
    "EUPL-1.2": {
        "name": "European Union Public License 1.2",
        "osi_approved": True,
        "fsf_free": True,
        "deprecated": False,
        "permissions": ["commercial-use", "modification", "distribution", "sublicense", "private-use"],
        "conditions": ["include-copyright", "include-license", "disclose-source"],
        "limitations": ["no-liability"],
        "compatibility": {"permissive": ["MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC"], "weak-copyleft": [], "copyleft": ["GPL-2.0", "GPL-3.0", "AGPL-3.0"]},
        "text": "European Union Public Licence\nV. 1.2\n\nEUPL (c) the European Union 2007, 2016\n\nThis European Union Public Licence (the \"EUPL\") applies to the work (as defined below) and is provided under the terms of this licence.\n\n1. Definitions\n2. Scope of the rights granted\n3. Communication of the source code\n4. Specific provisions on copyleft\n5. Liability and warranty\n6. Other provisions\n7. Language versions\n8. Acceptance of the Licence\n9. Additional agreements\n10. Versions of the Licence\n\nSee https://joinup.ec.europa.eu/collection/eupl/eupl-text-11-12 for full text."
    },
    "Zlib": {
        "name": "zlib License",
        "osi_approved": True,
        "fsf_free": True,
        "deprecated": False,
        "permissions": ["commercial-use", "modification", "distribution", "private-use"],
        "conditions": ["include-copyright"],
        "limitations": ["no-liability"],
        "compatibility": {"permissive": ["MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC", "MIT-0", "0BSD", "Unlicense", "CC0-1.0", "BSL-1.0"], "weak-copyleft": ["LGPL-2.1", "LGPL-3.0", "MPL-2.0"], "copyleft": ["GPL-2.0", "GPL-3.0"]},
        "text": "zlib License\n\nCopyright (c) [year] [copyright holders]\n\nThis software is provided 'as-is', without any express or implied warranty. In no event will the authors be held liable for any damages arising from the use of this software.\n\nPermission is granted to anyone to use this software for any purpose, including commercial applications, and to alter it and redistribute it freely, subject to the following restrictions:\n\n1. The origin of this software must not be misrepresented; you must not claim that you wrote the original software. If you use this software in a product, an acknowledgment in the product documentation would be appreciated but is not required.\n\n2. Altered source versions must be plainly marked as such, and must not be misrepresented as being the original software.\n\n3. This notice may not be removed or altered from any source distribution."
    },
}

COMPAT_NOTES = {
    ("MIT", "Apache-2.0"): "Compatible. Apache-2.0 code can be linked with MIT code; the combined work is distributed under Apache-2.0 terms.",
    ("MIT", "GPL-2.0"): "Compatible (GPL-2.0 compatible). MIT code can be incorporated into GPL-2.0 projects.",
    ("MIT", "GPL-3.0"): "Compatible. MIT code can be incorporated into GPL-3.0 projects.",
    ("Apache-2.0", "GPL-2.0"): "Incompatible. Apache-2.0 and GPL-2.0 are incompatible for combined works due to GPL-2.0 patent retaliation clause restrictions.",
    ("Apache-2.0", "GPL-3.0"): "Compatible (GPL-3.0 compatible). Apache-2.0 code can be included in GPL-3.0 projects.",
    ("GPL-2.0", "GPL-3.0"): "Compatible. GPL-2.0 code can be upgraded to GPL-3.0; combined works can be distributed under GPL-3.0.",
    ("GPL-2.0", "AGPL-3.0"): "Compatible. GPL-2.0 code may be linked with AGPL-3.0 code for combined works under AGPL-3.0.",
    ("GPL-3.0", "AGPL-3.0"): "Compatible. GPL-3.0 code may be linked with AGPL-3.0 code for combined works under AGPL-3.0.",
    ("LGPL-2.1", "GPL-2.0"): "Compatible. LGPL-2.1 code can be relicensed under GPL-2.0 (section 3 of LGPL-2.1).",
    ("LGPL-2.1", "GPL-3.0"): "Compatible. LGPL-2.1 code can be relicensed under GPL-3.0 (section 3 of LGPL-2.1).",
    ("LGPL-3.0", "GPL-2.0"): "Incompatible. LGPL-3.0 code cannot be used in GPL-2.0-only projects due to GPL-2.0's 'any later version' restriction.",
    ("LGPL-3.0", "GPL-3.0"): "Compatible. LGPL-3.0 and GPL-3.0 are compatible; combined work is GPL-3.0.",
    ("LGPL-2.1", "LGPL-3.0"): "Compatible. LGPL-2.1 code can be upgraded to LGPL-3.0.",
    ("MPL-2.0", "GPL-2.0"): "Compatible (GPL-2.0 compatible). MPL-2.0 code can be included in GPL-2.0 projects.",
    ("MPL-2.0", "GPL-3.0"): "Compatible. MPL-2.0 code can be included in GPL-3.0 projects.",
    ("MPL-2.0", "Apache-2.0"): "Compatible. MPL-2.0 code can be combined with Apache-2.0 code.",
    ("BSD-3-Clause", "Apache-2.0"): "Compatible. BSD-3-Clause code can be included in Apache-2.0 projects.",
    ("BSD-3-Clause", "GPL-3.0"): "Compatible. BSD-3-Clause code can be included in GPL-3.0 projects.",
    ("Unlicense", "Apache-2.0"): "Compatible. Unlicensed/public domain code can be used in any project.",
    ("CC0-1.0", "Apache-2.0"): "Compatible. CC0/public domain code can be used in any project.",
}

class LicenseServer(Server):
    def __init__(self):
        super().__init__("license")

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(name="lookup_license", description="Look up a license by SPDX identifier and return full details including permissions, conditions, and limitations", inputSchema={"type": "object", "properties": {"spdx_id": {"type": "string", "description": "SPDX identifier (e.g. MIT, Apache-2.0, GPL-3.0)"}}, "required": ["spdx_id"]}),
            Tool(name="list_licenses", description="List all available licenses with SPDX ID, name, and OSI approval status", inputSchema={"type": "object", "properties": {}}),
            Tool(name="search_licenses", description="Search licenses by name, SPDX ID, or keyword", inputSchema={"type": "object", "properties": {"query": {"type": "string", "description": "Search query to match against license names, IDs, or keywords"}}, "required": ["query"]}),
            Tool(name="license_text", description="Get the full text of a license by SPDX identifier", inputSchema={"type": "object", "properties": {"spdx_id": {"type": "string", "description": "SPDX identifier"}}, "required": ["spdx_id"]}),
            Tool(name="compare_licenses", description="Compare two licenses side by side showing differences in permissions, conditions, and limitations", inputSchema={"type": "object", "properties": {"spdx1": {"type": "string", "description": "First SPDX identifier"}, "spdx2": {"type": "string", "description": "Second SPDX identifier"}}, "required": ["spdx1", "spdx2"]}),
            Tool(name="check_compatibility", description="Check if two licenses are compatible for combined works", inputSchema={"type": "object", "properties": {"spdx1": {"type": "string", "description": "First SPDX identifier"}, "spdx2": {"type": "string", "description": "Second SPDX identifier"}}, "required": ["spdx1", "spdx2"]}),
            Tool(name="spdx_info", description="Get SPDX identifier metadata for a license", inputSchema={"type": "object", "properties": {"spdx_id": {"type": "string", "description": "SPDX identifier"}}, "required": ["spdx_id"]}),
        ]

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {}
        try:
            if name == "lookup_license":
                sid = args["spdx_id"].strip()
                if sid not in SPDX_LICENSES:
                    return [TextContent(type="text", text=json.dumps({"error": f"License '{sid}' not found"}))]
                info = dict(SPDX_LICENSES[sid])
                info["spdx_id"] = sid
                del info["text"]
                return [TextContent(type="text", text=json.dumps(info, indent=2))]

            elif name == "list_licenses":
                result = []
                for sid, info in sorted(SPDX_LICENSES.items()):
                    result.append({"spdx_id": sid, "name": info["name"], "osi_approved": info["osi_approved"], "fsf_free": info["fsf_free"]})
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            elif name == "search_licenses":
                q = args["query"].lower()
                result = []
                for sid, info in SPDX_LICENSES.items():
                    if q in sid.lower() or q in info["name"].lower() or q in " ".join(info["permissions"]).lower() or q in " ".join(info["conditions"]).lower():
                        result.append({"spdx_id": sid, "name": info["name"], "osi_approved": info["osi_approved"]})
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            elif name == "license_text":
                sid = args["spdx_id"].strip()
                if sid not in SPDX_LICENSES:
                    return [TextContent(type="text", text=json.dumps({"error": f"License '{sid}' not found"}))]
                return [TextContent(type="text", text=SPDX_LICENSES[sid]["text"])]

            elif name == "compare_licenses":
                s1, s2 = args["spdx1"].strip(), args["spdx2"].strip()
                if s1 not in SPDX_LICENSES:
                    return [TextContent(type="text", text=json.dumps({"error": f"License '{s1}' not found"}))]
                if s2 not in SPDX_LICENSES:
                    return [TextContent(type="text", text=json.dumps({"error": f"License '{s2}' not found"}))]
                l1, l2 = SPDX_LICENSES[s1], SPDX_LICENSES[s2]
                result = {
                    "license_1": {"spdx_id": s1, "name": l1["name"]},
                    "license_2": {"spdx_id": s2, "name": l2["name"]},
                    "permissions_1": l1["permissions"],
                    "permissions_2": l2["permissions"],
                    "permissions_only_in_1": [p for p in l1["permissions"] if p not in l2["permissions"]],
                    "permissions_only_in_2": [p for p in l2["permissions"] if p not in l1["permissions"]],
                    "conditions_1": l1["conditions"],
                    "conditions_2": l2["conditions"],
                    "conditions_only_in_1": [c for c in l1["conditions"] if c not in l2["conditions"]],
                    "conditions_only_in_2": [c for c in l2["conditions"] if c not in l1["conditions"]],
                    "limitations_1": l1["limitations"],
                    "limitations_2": l2["limitations"],
                }
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            elif name == "check_compatibility":
                s1, s2 = args["spdx1"].strip(), args["spdx2"].strip()
                if s1 not in SPDX_LICENSES:
                    return [TextContent(type="text", text=json.dumps({"error": f"License '{s1}' not found"}))]
                if s2 not in SPDX_LICENSES:
                    return [TextContent(type="text", text=json.dumps({"error": f"License '{s2}' not found"}))]
                note = COMPAT_NOTES.get((s1, s2)) or COMPAT_NOTES.get((s2, s1))
                compatible = note is not None
                l1_perms = set(SPDX_LICENSES[s1]["permissions"])
                l2_perms = set(SPDX_LICENSES[s2]["permissions"])
                if any("copyleft" in p or "same-license" in p for p in SPDX_LICENSES[s1]["conditions"]) and any("copyleft" in p or "same-license" in p for p in SPDX_LICENSES[s2]["conditions"]):
                    compatible = s1.replace("-", "").replace(".", "")[:3] == s2.replace("-", "").replace(".", "")[:3] or note is not None
                result = {
                    "license_1": s1,
                    "license_2": s2,
                    "compatible": compatible,
                    "note": note or "No specific compatibility information available. Review license terms carefully.",
                    "combined_restrictions": sorted(list(l1_perms - l2_perms) + list(l2_perms - l1_perms)),
                }
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            elif name == "spdx_info":
                sid = args["spdx_id"].strip()
                if sid not in SPDX_LICENSES:
                    return [TextContent(type="text", text=json.dumps({"error": f"License '{sid}' not found"}))]
                info = SPDX_LICENSES[sid]
                result = {
                    "spdx_id": sid,
                    "name": info["name"],
                    "osi_approved": info["osi_approved"],
                    "fsf_free": info["fsf_free"],
                    "deprecated": info["deprecated"],
                }
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            raise ValueError(f"Unknown tool: {name}")
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")

async def main():
    server = LicenseServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
