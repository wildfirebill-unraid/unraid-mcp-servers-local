import sys
import json
import os
import subprocess
from pathlib import Path
from typing import Any

from mcp.server import Server, stdio_server
from mcp.types import Tool, TextContent, Resource
import anyio

VIN_WEIGHTS = [8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2]

CHAR_VALUES = {
    '0': 0, '1': 1, '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9,
    'A': 1, 'B': 2, 'C': 3, 'D': 4, 'E': 5, 'F': 6, 'G': 7, 'H': 8,
    'J': 1, 'K': 2, 'L': 3, 'M': 4, 'N': 5, 'P': 7, 'R': 9,
    'S': 2, 'T': 3, 'U': 4, 'V': 5, 'W': 6, 'X': 7, 'Y': 8, 'Z': 9,
}

YEAR_CODES = {
    'A': 1980, 'B': 1981, 'C': 1982, 'D': 1983, 'E': 1984, 'F': 1985,
    'G': 1986, 'H': 1987, 'J': 1988, 'K': 1989, 'L': 1990, 'M': 1991,
    'N': 1992, 'P': 1993, 'R': 1994, 'S': 1995, 'T': 1996, 'V': 1997,
    'W': 1998, 'X': 1999, 'Y': 2000,
    '1': 2001, '2': 2002, '3': 2003, '4': 2004, '5': 2005,
    '6': 2006, '7': 2007, '8': 2008, '9': 2009,
}

WMI_TABLE = {
    "1C3": "Chrysler Group LLC",
    "1C4": "Chrysler Group LLC",
    "1C6": "Chrysler Group LLC",
    "1D3": "Dodge (Mexico)",
    "1F9": "FWD Corp.",
    "1FA": "Ford Motor Company",
    "1FB": "Ford Motor Company",
    "1FC": "Ford Motor Company",
    "1FD": "Ford Motor Company",
    "1FM": "Ford Motor Company",
    "1FT": "Ford Motor Company",
    "1FU": "Freightliner",
    "1FV": "Freightliner",
    "1G0": "General Motors",
    "1G1": "Chevrolet",
    "1G2": "Pontiac",
    "1G3": "Oldsmobile",
    "1G4": "Buick",
    "1G6": "Cadillac",
    "1G8": "Saturn",
    "1GC": "Chevrolet Truck",
    "1GD": "GMC Truck",
    "1GT": "GMC Truck",
    "1H4": "Dodge Trucks (Mexico)",
    "1H6": "Daimler Trucks North America",
    "1HA": "Daimler Trucks North America",
    "1HD": "Harley-Davidson",
    "1J4": "Jeep",
    "1J8": "Jeep",
    "1L9": "Lincoln-Mercury (Mexico)",
    "1M1": "Mack Trucks",
    "1M2": "Mack Trucks",
    "1M4": "Mack Trucks",
    "1M9": "Mack Trucks",
    "1N4": "Nissan (USA)",
    "1N6": "Nissan (USA)",
    "1NX": "Toyota (USA)",
    "1P3": "Plymouth",
    "1R9": "Roadrunner Hay Squeeze",
    "1VW": "Volkswagen (USA)",
    "1X9": "U-Haul",
    "1XK": "Kenworth",
    "1XP": "Peterbilt",
    "1YV": "Mazda (USA)",
    "1ZV": "Ford (Mexico)",
    "2A5": "Dodge (Canada)",
    "2B1": "Dodge (Canada)",
    "2B3": "Dodge (Canada)",
    "2B7": "Dodge (Canada)",
    "2C3": "Chrysler (Canada)",
    "2CG": "Chrysler (Canada)",
    "2CN": "Chrysler (Canada)",
    "2D4": "Dodge (Canada)",
    "2F": "Ford (Canada)",
    "2FA": "Ford (Canada)",
    "2FB": "Ford (Canada)",
    "2FC": "Ford (Canada)",
    "2FM": "Ford (Canada)",
    "2FT": "Ford (Canada)",
    "2G1": "Chevrolet (Canada)",
    "2G2": "Pontiac (Canada)",
    "2G3": "Oldsmobile (Canada)",
    "2G4": "Buick (Canada)",
    "2G5": "GM Canada",
    "2G9": "GM Canada",
    "2HG": "Honda (Canada)",
    "2HK": "Honda (Canada)",
    "2HM": "Hyundai (Canada)",
    "2LM": "Lincoln-Mercury (Canada)",
    "2M": "Mercury (Canada)",
    "2MD": "Mercury (Canada)",
    "2ME": "Mercury (Canada)",
    "2MR": "Mercury (Canada)",
    "2P3": "Plymouth (Canada)",
    "2T3": "Toyota (Canada)",
    "2T4": "Toyota (Canada)",
    "2WK": "Western Star Trucks",
    "2WM": "Western Star Trucks",
    "3C3": "Chrysler (Mexico)",
    "3C4": "Chrysler (Mexico)",
    "3D3": "Dodge (Mexico)",
    "3D4": "Dodge (Mexico)",
    "3FA": "Ford (Mexico)",
    "3FE": "Ford (Mexico)",
    "3G1": "Chevrolet (Mexico)",
    "3G2": "Pontiac (Mexico)",
    "3G3": "Oldsmobile (Mexico)",
    "3G4": "Buick (Mexico)",
    "3G5": "GMC (Mexico)",
    "3H3": "Daimler-Chrysler (Mexico)",
    "3HG": "Honda (Mexico)",
    "3LN": "Lincoln",
    "3MA": "Mazda (Mexico)",
    "3MB": "Mazda (Mexico)",
    "3MD": "Mazda (Mexico)",
    "3ME": "Mazda (Mexico)",
    "3N": "Nissan (Mexico)",
    "3P3": "Plymouth (Mexico)",
    "3VW": "Volkswagen (Mexico)",
    "4A4": "Mitsubishi (USA)",
    "4AG": "Mitsubishi (USA)",
    "4F2": "Mazda (USA)",
    "4F4": "Mazda (USA)",
    "4G": "Mitsubishi (USA)",
    "4J": "Mercedes-Benz (USA)",
    "4M": "Mercury (USA)",
    "4S4": "Subaru-Isuzu Automotive",
    "4S6": "Subaru-Isuzu Automotive",
    "4S7": "Subaru-Isuzu Automotive",
    "4T1": "Toyota (USA)",
    "4T3": "Toyota (USA)",
    "4T4": "Toyota (USA)",
    "4TA": "Toyota (USA)",
    "4US": "BMW (USA)",
    "4UZ": "Fiat (USA)",
    "4V1": "Volvo Trucks",
    "4V2": "Volvo Trucks",
    "4V3": "Volvo Trucks",
    "4V4": "Volvo Trucks",
    "4V5": "Volvo Trucks",
    "4V6": "Volvo Trucks",
    "4VL": "Volvo Trucks",
    "4VM": "Volvo Trucks",
    "4VZ": "Volvo Trucks",
    "5GA": "Buick (USA)",
    "5GD": "GMC (USA)",
    "5GN": "GMC (USA)",
    "5GZ": "GMC (USA)",
    "5J6": "Honda (USA)",
    "5L1": "Lincoln (USA)",
    "5LD": "Lincoln (USA)",
    "5LP": "Lincoln (USA)",
    "5N1": "Nissan (USA)",
    "5NP": "Hyundai (USA)",
    "5T": "Toyota (USA)",
    "5TD": "Toyota (USA)",
    "5UM": "BMW (USA)",
    "5UX": "BMW (USA)",
    "5VC": "Fiat (USA)",
    "5XX": "Kia (USA)",
    "5XY": "Kia (USA)",
    "5XZ": "Kia (USA)",
    "5Y2": "Toyota (USA)",
    "5YJ": "Tesla",
    "5YM": "Tesla",
    "6AB": "GM Holden (Australia)",
    "6F5": "Ford (Australia)",
    "6FP": "Ford (Australia)",
    "6G1": "GM Holden (Australia)",
    "6G2": "Pontiac (Australia)",
    "6H8": "GM Holden (Australia)",
    "6MM": "Mitsubishi (Australia)",
    "6T1": "Toyota (Australia)",
    "6U9": "Privately Imported (Australia)",
    "7A3": "Honda (New Zealand)",
    "7F8": "Massey Ferguson",
    "8AD": "Peugeot (Argentina)",
    "8AF": "Ford (Argentina)",
    "8AG": "Chevrolet (Argentina)",
    "8AJ": "Toyota (Argentina)",
    "8AP": "Fiat (Argentina)",
    "8AT": "Iveco (Argentina)",
    "8AW": "Volkswagen (Argentina)",
    "8BR": "Mercedes-Benz (Argentina)",
    "8GD": "Peugeot (Chile)",
    "8GG": "Chevrolet (Chile)",
    "8X": "Scania",
    "8Z1": "Chevrolet (Venezuela)",
    "8Z2": "Ford (Venezuela)",
    "8Z6": "Fiat (Venezuela)",
    "9BD": "Fiat (Brazil)",
    "9BF": "Ford (Brazil)",
    "9BG": "Chevrolet (Brazil)",
    "9BM": "Mercedes-Benz (Brazil)",
    "9BR": "Toyota (Brazil)",
    "9BS": "Scania (Brazil)",
    "9BV": "Volvo (Brazil)",
    "9BW": "Volkswagen (Brazil)",
    "9C2": "Honda (Brazil)",
    "9FB": "Renault (Colombia)",
    "9GA": "Chevrolet (Colombia)",
    "J": "Japan",
    "JA": "Isuzu",
    "JB": "Mitsubishi (Japan)",
    "JC": "Mitsubishi (Japan)",
    "JD": "Daihatsu",
    "JF": "Fuji Heavy Industries (Subaru)",
    "JG": "Mitsubishi (Japan)",
    "JH": "Honda",
    "JJ": "Mitsubishi (Japan)",
    "JK": "Mazda",
    "JL": "Mitsubishi (Japan)",
    "JM": "Mazda",
    "JN": "Nissan",
    "JP": "Nissan",
    "JR": "Isuzu",
    "JS": "Suzuki",
    "JT": "Toyota",
    "JV": "Mitsubishi (Japan)",
    "JW": "Mazda",
    "JX": "Mitsubishi (Japan)",
    "JY": "Yamaha",
    "K": "Korea",
    "KM": "Hyundai",
    "KN": "Kia",
    "KNA": "Kia",
    "KNB": "Kia",
    "KNC": "Kia",
    "KND": "Kia",
    "KNE": "Kia",
    "KNF": "Kia",
    "KNG": "Kia",
    "KNH": "Kia",
    "KPA": "Ssangyong",
    "KPT": "Ssangyong",
    "KLA": "Daewoo",
    "KLB": "Daewoo",
    "KL1": "GM Korea",
    "L": "China",
    "L6T": "Geely",
    "LBE": "Beijing Hyundai",
    "LBU": "Dongfeng Motor",
    "LC1": "Chang'an Ford",
    "LDC": "Dongfeng Peugeot",
    "LDY": "Zhongtong Coach",
    "LEN": "Nanjing Fiat",
    "LEP": "FAW Toyota",
    "LFV": "FAW Volkswagen",
    "LGA": "Dongfeng Commercial",
    "LGH": "Dongfeng Motor",
    "LGW": "Great Wall",
    "LHG": "Guangzhou Honda",
    "LJ1": "JAC",
    "LJ8": "Zotye",
    "LKL": "Jiangling",
    "LL6": "Hunan Changfeng",
    "LL8": "JMC",
    "LMW": "Changan Suzuki",
    "LNB": "Beijing Auto",
    "LNY": "Yuejin",
    "LPA": "Guangzhou Peugeot",
    "LPH": "Changan Suzuki",
    "LRA": "Dongfeng Liuzhou",
    "LRB": "Shanghai GM",
    "LS1": "SAIC Motor",
    "LS5": "Changan Automobile",
    "LSG": "Shanghai GM",
    "LSJ": "SAIC Motor",
    "LSY": "Brilliance",
    "LTA": "Zonda Auto",
    "LTD": "Dongfeng Yueda Kia",
    "LTV": "Ford (China)",
    "LUC": "Guangqi Honda",
    "LVS": "Changan Ford",
    "LVV": "Chery",
    "LVZ": "Dongfeng Sokon",
    "LWM": "Shanqi",
    "LZG": "Shaanxi Automobile",
    "LZP": "Zhongshan Guangkai",
    "LZY": "Yutong",
    "LZZ": "Chongqing Huapu",
    "M": "India",
    "MA": "Maruti Suzuki",
    "MA1": "Mahindra",
    "MA3": "Maruti Suzuki",
    "MA7": "Honda (India)",
    "MAL": "Mahindra",
    "MBH": "Skoda (India)",
    "MBJ": "Toyota (India)",
    "MBR": "Mercedes-Benz (India)",
    "MCA": "Fiat (India)",
    "MCB": "GM (India)",
    "MCD": "Ford (India)",
    "MCE": "Volkswagen (India)",
    "MCF": "Hyundai (India)",
    "MCG": "Tata Daewoo",
    "MDH": "Nissan (India)",
    "MEC": "Tata Motors",
    "MEE": "Renault (India)",
    "MEG": "Ashok Leyland",
    "MEX": "Volvo (India)",
    "MH": "Volkswagen (India)",
    "MH1": "Hindustan Motors",
    "MH2": "Bajaj Auto",
    "MH4": "Royal Enfield",
    "MH6": "Honda (India)",
    "MH8": "Eicher Motors",
    "MJ9": "Polaris (India)",
    "ML": "India commercial",
    "MM": "Hyundai (India)",
    "MMB": "GM Korea (India)",
    "MMC": "Mitsubishi (India)",
    "MMM": "Chevrolet (India)",
    "MMT": "Mitsubishi (India)",
    "MN": "Ford (India)",
    "MP": "Tata (India)",
    "MPA": "ICML",
    "MR": "Nissan (India)",
    "MR0": "Toyota (India)",
    "MS": "Suzuki",
    "MS0": "Force Motors",
    "MS3": "Suzuki",
    "MT": "Mercedes-Benz (India)",
    "MT1": "John Deere (India)",
    "MT9": "Škoda (India)",
    "N": "Turkey",
    "NAA": "Isuzu (Turkey)",
    "NAC": "Ford Otosan",
    "NAD": "Hyundai Assan",
    "NLA": "Honda (Turkey)",
    "NLE": "Mercedes-Benz Turk",
    "NLT": "Temsa",
    "NMA": "M.A.N. (Turkey)",
    "NMB": "BMC (Turkey)",
    "NMC": "BMC (Turkey)",
    "NLH": "Hyundai (Turkey)",
    "NNA": "Toyota (Turkey)",
    "NP": "Otokar",
    "NT": "Karsan",
    "P": "Thailand",
    "PLA": "BMW (Thailand)",
    "PLP": "Nissan (Thailand)",
    "PLR": "Honda (Thailand)",
    "PLS": "Suzuki (Thailand)",
    "PLU": "SSUP",
    "PLV": "Ford (Thailand)",
    "PMB": "Mitsubishi (Thailand)",
    "PME": "Mazda (Thailand)",
    "PMM": "Chevrolet (Thailand)",
    "PNT": "Toyota (Thailand)",
    "PPV": "GM (Thailand)",
    "PR1": "Mazda (Thailand)",
    "PSA": "Peugeot (Thailand)",
    "PT1": "Tata (Thailand)",
    "PTA": "Isuzu (Thailand)",
    "PTC": "Hino (Thailand)",
    "S": "United Kingdom",
    "SA": "Land Rover",
    "SAB": "Optare",
    "SAD": "Jaguar",
    "SAF": "Ineos Automotive",
    "SAL": "Land Rover",
    "SAR": "Rover",
    "SB1": "Toyota (UK)",
    "SB6": "LDV",
    "SBM": "McLaren",
    "SCA": "Rolls-Royce",
    "SCB": "Bentley",
    "SCC": "Lotus",
    "SCE": "DeLorean",
    "SCF": "Aston Martin",
    "SCK": "Caterpillar",
    "SDB": "Peugeot (UK)",
    "SFD": "Alexander Dennis",
    "SGD": "MCI (UK)",
    "SHH": "Honda (UK)",
    "SJN": "Nissan (UK)",
    "SKF": "Vauxhall",
    "SLP": "LDV",
    "SMT": "Leyland Trucks",
    "SNT": "Nissan (UK)",
    "SPD": "Peugeot (UK)",
    "SUL": "Foden Trucks",
    "SUP": "IBC Vehicles",
    "SV9": "LDV",
    "SWV": "LDV",
    "T": "Switzerland",
    "TCC": "Micro Compact Car (Smart)",
    "TDM": "Queen's University Belfast",
    "TK9": "Bedford Vehicles",
    "TMB": "Škoda (Czech)",
    "TMK": "Karosa",
    "TMT": "Tatra",
    "TN9": "Tatra",
    "TRA": "Ikarus Bus",
    "TRU": "Audi (Hungary)",
    "TSM": "Suzuki (Hungary)",
    "TSP": "Škoda (Czech)",
    "TSU": "Rába",
    "TW1": "Citroën (Portugal)",
    "TYA": "Mitsubishi (Portugal)",
    "TYB": "Toyota (Portugal)",
    "U": "Portugal",
    "U5": "Dacia",
    "U6": "Renault (Portugal)",
    "U9": "Unimog",
    "UA": "Renault (France)",
    "UAB": "Renault Trucks",
    "UAH": "Renault Trucks",
    "UAP": "Renault Trucks",
    "UAT": "Renault Trucks",
    "UAU": "Irisbus",
    "UF": "Toyota (France)",
    "UH": "Peugeot (France)",
    "V": "France",
    "VBC": "Citroën",
    "VF1": "Renault",
    "VF2": "Renault",
    "VF3": "Peugeot",
    "VF4": "Citroën",
    "VF6": "Renault Trucks",
    "VF7": "Citroën",
    "VF8": "Mitsubishi (France)",
    "VF9": "Irisbus",
    "VFA": "Heuliez",
    "VFD": "M.A.N. (France)",
    "VFE": "Iveco (France)",
    "VFG": "Irisbus",
    "VFJ": "Irisbus",
    "VFM": "Renault Trucks",
    "VFO": "Renault Trucks",
    "VFR": "Renault Trucks",
    "VFT": "Renault Trucks",
    "VFU": "Scania (France)",
    "VG": "Renault (Spain)",
    "VHV": "Renault Trucks",
    "VJ": "Renault",
    "VK": "Kenworth (France)",
    "VL": "Peugeot (France)",
    "VM": "Renault Trucks",
    "VNE": "Irisbus",
    "VNK": "Toyota (France)",
    "VNV": "Renault Trucks",
    "VR": "Mercedes-Benz (France)",
    "VS": "Renault Trucks",
    "VSE": "Irisbus",
    "VSK": "Nissan (Spain)",
    "VSS": "SEAT",
    "VSX": "Renault Trucks",
    "VSY": "M.A.N. (Spain)",
    "VTD": "Renault Trucks",
    "VTN": "Renault Trucks",
    "VTP": "Renault Trucks",
    "VTT": "Renault Trucks",
    "VV9": "Renault Trucks",
    "VX": "Iveco (France)",
    "W": "Germany",
    "W0L": "Opel",
    "W09": "Ruf Automobile",
    "WAP": "BMW",
    "WAU": "Audi",
    "WBA": "BMW",
    "WBS": "BMW M",
    "WBY": "BMW i",
    "WCD": "MAN",
    "WDA": "Daimler AG",
    "WDB": "Mercedes-Benz",
    "WDC": "Mercedes-Benz",
    "WDD": "Mercedes-Benz",
    "WDP": "Mercedes-Benz",
    "WEA": "Mercedes-Benz",
    "WEB": "Mercedes-Benz",
    "WFC": "Iveco Magirus",
    "WMA": "MAN",
    "WME": "smart",
    "WMW": "MINI",
    "WMX": "Mercedes-AMG",
    "WOL": "Opel",
    "WP0": "Porsche",
    "WP1": "Porsche Cayenne",
    "WUA": "Audi Sport",
    "WVG": "Volkswagen (Multipurpose)",
    "WVW": "Volkswagen (Passenger)",
    "WV1": "Volkswagen (Commercial)",
    "WV2": "Volkswagen (Bus/Van)",
    "X": "Europe (various)",
    "XLB": "Volvo (Netherlands)",
    "XLC": "NedCar",
    "XLE": "Scania (Netherlands)",
    "XLF": "DAF Trucks",
    "XLR": "DAF Trucks",
    "XS8": "DAF Trucks",
    "XTA": "AvtoVAZ (Lada)",
    "XTC": "KAMAZ",
    "XTH": "GAZ",
    "XTU": "UAZ",
    "XUF": "ZAZ",
    "XWB": "UZ-Daewoo",
    "XWF": "Avtotor",
    "XWK": "IzhAvto",
    "XW8": "Volkswagen (Russia)",
    "XWY": "GM-AvtoVAZ",
    "X1B": "Škoda (Russia)",
    "Y": "Belgium/Spain/Sweden",
    "YAR": "Peugeot (Belgium)",
    "YCM": "Mazda (Belgium)",
    "YE1": "Toyota (Belgium)",
    "YH2": "Ford (Belgium)",
    "YJS": "Volvo Trucks (Sweden)",
    "YK1": "Saab",
    "YS2": "Scania (Sweden)",
    "YS3": "Saab",
    "YS4": "Scania (Sweden)",
    "YT9": "Koenigsegg",
    "YV1": "Volvo Cars",
    "YV4": "Volvo Cars",
    "YV8": "Volvo Cars",
    "YVV": "Volvo Trucks (Sweden)",
    "YVU": "Volvo Trucks (Sweden)",
    "YVX": "Volvo Trucks (Sweden)",
    "ZA": "Italy",
    "ZA9": "Ducati",
    "ZAA": "Autobianchi",
    "ZAM": "Maserati",
    "ZAP": "Piaggio",
    "ZAR": "Alfa Romeo",
    "ZAS": "Maserati",
    "ZAZ": "Fiat (Italy)",
    "ZBH": "Fiat (Italy)",
    "ZBN": "Fiat (Italy)",
    "ZBP": "Fiat (Italy)",
    "ZBR": "Fiat (Italy)",
    "ZCC": "Autobianchi",
    "ZC2": "Fiat (Italy)",
    "ZCF": "Iveco",
    "ZD0": "Yamaha (Italy)",
    "ZD4": "Aprilia",
    "ZDC": "Honda (Italy)",
    "ZDM": "Ducati",
    "ZDV": "Moto Guzzi",
    "ZE1": "Peugeot (Italy)",
    "ZFA": "Fiat",
    "ZFC": "Fiat (Italy)",
    "ZFF": "Ferrari",
    "ZFM": "Fiat (Italy)",
    "ZFR": "Fiat (Italy)",
    "ZGA": "Iveco",
    "ZGU": "Moto Guzzi",
    "ZHW": "Lamborghini",
    "ZJA": "Aprilia",
    "ZJM": "Fiat (Italy)",
    "ZJN": "Fiat (Italy)",
    "ZJS": "Fiat (Italy)",
    "ZKH": "Iveco",
    "ZLA": "Lancia",
    "ZLC": "Fiat (Italy)",
    "ZLD": "Fiat (Italy)",
    "ZLE": "Fiat (Italy)",
    "ZLF": "Fiat (Italy)",
    "ZLG": "Iveco",
    "ZLH": "Iveco",
    "ZLI": "Iveco",
    "ZLM": "Fiat (Italy)",
    "ZLU": "Fiat (Italy)",
    "ZLV": "Fiat (Italy)",
    "ZLW": "Fiat (Italy)",
    "ZLY": "Fiat (Italy)",
    "ZMA": "Fiat (Italy)",
    "ZMB": "Fiat (Italy)",
    "ZMC": "Fiat (Italy)",
    "ZMD": "Fiat (Italy)",
    "ZME": "Fiat (Italy)",
    "ZMF": "Fiat (Italy)",
    "ZMG": "Fiat (Italy)",
    "ZMH": "Fiat (Italy)",
    "ZMI": "Fiat (Italy)",
    "ZMJ": "Fiat (Italy)",
    "ZMK": "Fiat (Italy)",
    "ZML": "Fiat (Italy)",
    "ZMM": "Fiat (Italy)",
    "ZMN": "Fiat (Italy)",
    "ZMP": "Fiat (Italy)",
    "ZMQ": "Fiat (Italy)",
    "ZMR": "Fiat (Italy)",
    "ZMS": "Fiat (Italy)",
    "ZMT": "Fiat (Italy)",
    "ZMU": "Fiat (Italy)",
    "ZMY": "Fiat (Italy)",
    "ZMX": "Fiat (Italy)",
    "ZN6": "Aprilia",
    "ZN9": "Aprilia",
    "ZNE": "Fiat (Italy)",
    "ZNN": "Fiat (Italy)",
    "ZNP": "Fiat (Italy)",
    "ZNT": "Fiat (Italy)",
    "ZNW": "Fiat (Italy)",
    "ZNY": "Fiat (Italy)",
    "ZPA": "Piaggio",
    "ZPC": "Piaggio",
    "ZPK": "Piaggio",
    "ZPL": "Piaggio",
    "ZPN": "Piaggio",
    "ZPP": "Piaggio",
    "ZPR": "Piaggio",
    "ZPS": "Piaggio",
    "ZPT": "Piaggio",
    "ZPU": "Piaggio",
    "ZPV": "Piaggio",
    "ZPW": "Piaggio",
    "ZPY": "Piaggio",
    "ZR0": "Fiat (Italy)",
    "ZTZ": "Iveco",
}

COUNTRY_MAP = {
    "1": "USA", "2": "Canada", "3": "Mexico", "4": "USA",
    "5": "USA", "6": "Australia", "7": "New Zealand",
    "8": "Argentina", "9": "Brazil",
    "A": "South Africa", "B": "Ivory Coast",
    "C": "Benin", "D": "Egypt",
    "E": "Ethiopia", "F": "Morocco",
    "G": "Ghana", "H": "Kenya",
    "J": "Japan", "K": "South Korea",
    "L": "China", "M": "India",
    "N": "Turkey", "P": "Thailand",
    "R": "Taiwan", "S": "United Kingdom",
    "T": "Switzerland", "U": "Portugal",
    "V": "France", "W": "Germany",
    "X": "Russia / CIS", "Y": "Belgium / Spain / Sweden",
    "Z": "Italy",
}


def _sanitize_vin(vin: str) -> str:
    return vin.strip().upper()


def _is_valid_structure(vin: str) -> list[str]:
    errors = []
    if len(vin) != 17:
        errors.append(f"Length must be 17 characters, got {len(vin)}")
    allowed = set("0123456789ABCDEFGHJKLMNPRSTUVWXYZ")
    for i, c in enumerate(vin):
        if c not in allowed:
            errors.append(f"Invalid character '{c}' at position {i+1} (I, O, Q not allowed)")
    return errors


def _calc_check_digit(vin: str) -> str:
    total = 0
    for i, c in enumerate(vin):
        val = CHAR_VALUES.get(c, 0)
        total += val * VIN_WEIGHTS[i]
    rem = total % 11
    return 'X' if rem == 10 else str(rem)


def _validate_check_digit(vin: str) -> bool:
    expected = _calc_check_digit(vin)
    return vin[8] == expected


def _decode_year(year_char: str) -> int | None:
    base = YEAR_CODES.get(year_char)
    if base is None:
        return None
    cycles = (2026 - base) // 30
    if cycles > 0:
        base += cycles * 30
    if base > 2026:
        base -= 30
    return base


def _lookup_wmi(wmi: str) -> dict:
    wmi = wmi[:3]
    exact = WMI_TABLE.get(wmi)
    if exact:
        return {"wmi": wmi, "manufacturer": exact}
    for prefix, mfr in WMI_TABLE.items():
        if wmi.startswith(prefix):
            return {"wmi": wmi, "manufacturer": mfr}
    country_code = wmi[0] if wmi else ""
    country = COUNTRY_MAP.get(country_code, "Unknown")
    return {"wmi": wmi, "manufacturer": f"Unknown (country: {country})", "country": country}


class VinServer(Server):
    def __init__(self):
        super().__init__("vin")
        self._init_env()

    def _init_env(self):
        pass

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(name="validate_vin", description="Validate a VIN (17 chars, no I/O/Q, check digit)", inputSchema={"type": "object", "properties": {"vin": {"type": "string", "description": "17-character VIN"}}, "required": ["vin"]}),
            Tool(name="decode_vin", description="Parse VIN into WMI, VDS, VIS, year, check digit", inputSchema={"type": "object", "properties": {"vin": {"type": "string", "description": "17-character VIN"}}, "required": ["vin"]}),
            Tool(name="vin_info", description="Get VIN manufacturer info from WMI lookup table", inputSchema={"type": "object", "properties": {"vin": {"type": "string", "description": "17-character VIN"}}, "required": ["vin"]}),
            Tool(name="year_from_vin", description="Decode model year from VIN character 10", inputSchema={"type": "object", "properties": {"vin": {"type": "string", "description": "17-character VIN"}}, "required": ["vin"]}),
            Tool(name="vin_fingerprint", description="Compact summary of VIN structure validity", inputSchema={"type": "object", "properties": {"vin": {"type": "string", "description": "17-character VIN"}}, "required": ["vin"]}),
        ]

    async def call_tool(self, name: str, arguments: dict | None) -> list[TextContent]:
        args = arguments or {}
        try:
            if name == "validate_vin":
                vin = _sanitize_vin(args.get("vin", ""))
                struct_errors = _is_valid_structure(vin)
                if struct_errors:
                    result = {"valid": False, "vin": vin, "errors": struct_errors}
                else:
                    cd_ok = _validate_check_digit(vin)
                    expected = _calc_check_digit(vin)
                    result = {"valid": cd_ok, "vin": vin, "check_digit": vin[8], "expected_check_digit": expected, "check_digit_match": cd_ok}
                    if not cd_ok:
                        result["reason"] = "Check digit mismatch"
                return [TextContent(type="text", text=json.dumps(result))]

            if name == "decode_vin":
                vin = _sanitize_vin(args.get("vin", ""))
                struct_errors = _is_valid_structure(vin)
                if struct_errors:
                    return [TextContent(type="text", text=json.dumps({"error": "Invalid VIN structure", "vin": vin, "errors": struct_errors}))]
                wmi = vin[0:3]
                vds = vin[3:8]
                check = vin[8]
                vis = vin[9:17]
                year_char = vin[9]
                plant = vin[10]
                serial = vin[11:17]
                year = _decode_year(year_char)
                cd_expected = _calc_check_digit(vin)
                result = {"vin": vin, "wmi": wmi, "vds": vds, "check_digit": check, "check_digit_expected": cd_expected, "check_digit_valid": check == cd_expected, "vis": vis, "year_code": year_char, "decoded_year": year, "plant_code": plant, "serial": serial}
                return [TextContent(type="text", text=json.dumps(result))]

            if name == "vin_info":
                vin = _sanitize_vin(args.get("vin", ""))
                struct_errors = _is_valid_structure(vin)
                if struct_errors:
                    return [TextContent(type="text", text=json.dumps({"error": "Invalid VIN structure", "vin": vin, "errors": struct_errors}))]
                wmi = vin[0:3]
                info = _lookup_wmi(wmi)
                country_code = wmi[0]
                country = COUNTRY_MAP.get(country_code, "Unknown")
                result = {"vin": vin, "wmi": wmi, "manufacturer": info["manufacturer"], "country": country, "year_code": vin[9], "decoded_year": _decode_year(vin[9])}
                if "country" in info:
                    result["country_detail"] = info["country"]
                return [TextContent(type="text", text=json.dumps(result))]

            if name == "year_from_vin":
                vin = _sanitize_vin(args.get("vin", ""))
                struct_errors = _is_valid_structure(vin)
                if struct_errors:
                    return [TextContent(type="text", text=json.dumps({"error": "Invalid VIN structure", "vin": vin, "errors": struct_errors}))]
                year_char = vin[9]
                year = _decode_year(year_char)
                possible_years = [year]
                if year:
                    possible_years = sorted({year + 30 * offset for offset in range(-2, 3) if 1970 <= year + 30 * offset <= 2040})
                result = {"vin": vin, "year_code_character": year_char, "decoded_year": year, "possible_years": sorted(possible_years) if year else []}
                return [TextContent(type="text", text=json.dumps(result))]

            if name == "vin_fingerprint":
                vin = _sanitize_vin(args.get("vin", ""))
                struct_errors = _is_valid_structure(vin)
                if struct_errors:
                    return [TextContent(type="text", text=json.dumps({"error": "Invalid VIN structure", "vin": vin, "errors": struct_errors}))]
                wmi = vin[0:3]
                mfr = _lookup_wmi(wmi)["manufacturer"]
                year = _decode_year(vin[9])
                cd_valid = _validate_check_digit(vin)
                country_code = wmi[0]
                country = COUNTRY_MAP.get(country_code, "Unknown")
                result = {"vin": vin, "length": 17, "wmi": wmi, "manufacturer": mfr, "country": country, "year_code": vin[9], "decoded_year": year, "check_digit_valid": cd_valid, "vds": vin[3:8], "serial": vin[11:17]}
                return [TextContent(type="text", text=json.dumps(result))]

            raise ValueError(f"Unknown tool: {name}")
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    async def list_resources(self) -> list[Resource]:
        return []

    async def read_resource(self, uri: str) -> str:
        raise ValueError(f"Unknown resource: {uri}")


async def main():
    server = VinServer()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.list_tools, server.call_tool, server.list_resources, server.read_resource)

if __name__ == "__main__":
    anyio.run(main)
