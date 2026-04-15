"""Legal domain constants for the Indian legal system.

Defines mappings and reference data used across the platform
for statutory cross-referencing.
"""

from typing import Final

# ---------------------------------------------------------------------------
# IPC → BNS section mapping  (Indian Penal Code, 1860 → Bharatiya Nyaya
# Sanhita, 2023 — effective 1 July 2024)
# ---------------------------------------------------------------------------

IPC_TO_BNS_MAP: Final[dict[str, str]] = {
    # ── General exceptions (Chapter IV, IPC 76–106) ──────────────────────
    "76": "14",  # Act done by person bound / by mistake of fact believing bound by law
    "79": "16",  # Act done by person justified by law / mistake of fact
    "80": "17",  # Accident in doing a lawful act
    "81": "18",  # Act likely to cause harm, done without criminal intent to prevent other harm
    "82": "19",  # Act of a child under seven years
    "83": "20",  # Act of a child above seven and under twelve of immature understanding
    "84": "22",  # Act of a person of unsound mind
    "85": "23",  # Act of a person incapable of judgment by reason of intoxication
    "86": "24",  # Offence requiring particular knowledge or intent — intoxicated person
    "87": "25",  # Act not intended and not known to be likely to cause death or GH
    "88": "26",  # Act not intended to cause death, done by consent in good faith
    "89": "27",  # Act done in good faith for benefit of child or insane person
    "90": "28",  # Consent known to be given under fear or misconception
    "91": "29",  # Exclusion of acts which are offences independently of harm caused
    "92": "30",  # Act done in good faith for benefit of a person without consent
    "96": "34",  # Things done in private defence
    "97": "35",  # Right of private defence of body and property
    "99": "36",  # Acts against which there is no right of private defence
    "100": "37",  # When the right of private defence of body extends to causing death
    "101": "38",  # When such right extends to causing any harm other than death
    "102": "39",  # Commencement and continuance of right of private defence of body
    "103": "40",  # When right of private defence of property extends to causing death
    "104": "41",  # When such right extends to causing any harm other than death
    "105": "42",  # Commencement and continuance of right of private defence of property
    "106": "43",  # Right of private defence against deadly assault when risk of harm to innocent
    # ── Abetment (IPC 107–120) ───────────────────────────────────────────
    "107": "45",  # Abetment of a thing
    "108": "46",  # Abettor
    "109": "47",  # Punishment of abetment if act abetted is committed
    "110": "48",  # Punishment of abetment if person abetted does act with different intention
    "111": "49",  # Liability of abettor when one act abetted and different act done
    "112": "50",  # Abettor when liable to cumulative punishment for act abetted and for act done
    "113": "51",  # Liability of abettor for an effect caused by act abetted different from intended
    "114": "52",  # Abettor present when offence is committed
    "115": "53",  # Abetment of offence punishable with death or imprisonment for life
    "116": "54",  # Abetment of offence punishable with imprisonment
    "117": "55",  # Abetting commission of offence by public or by more than ten persons
    "118": "56",  # Concealing design to commit offence punishable with death or imprisonment for life
    "119": "57",  # Public servant concealing design to commit offence
    "120": "58",  # Concealing design to commit offence punishable with imprisonment
    # ── Criminal conspiracy (IPC 120A–120B) ──────────────────────────────
    "120A": "61(1)",  # Definition of criminal conspiracy
    "120B": "61",  # Punishment of criminal conspiracy
    # ── Common intention and joint liability ─────────────────────────────
    "34": "3(5)",  # Acts done by several persons in furtherance of common intention
    "35": "3(6)",  # When such an act is criminal by reason of being done with criminal knowledge or intention
    "36": "3(7)",  # Effect caused partly by act and partly by omission
    "37": "3(8)",  # Co-operation by doing one of several acts constituting an offence
    "38": "3(9)",  # Persons concerned in criminal act may be guilty of different offences
    # ── Unlawful assembly and rioting (IPC 141–158) ──────────────────────
    "141": "189",  # Unlawful assembly
    "142": "189(1)",  # Membership of unlawful assembly
    "143": "189(2)",  # Punishment for being member of unlawful assembly
    "144": "189(3)",  # Joining unlawful assembly armed with deadly weapon
    "145": "189(4)",  # Joining or continuing in unlawful assembly knowing it has been commanded to disperse
    "146": "191",  # Rioting
    "147": "191",  # Punishment for rioting
    "148": "192",  # Rioting armed with deadly weapon
    "149": "190",  # Every member of unlawful assembly guilty of offence committed
    "150": "190(2)",  # Hiring or conniving at hiring of persons to join unlawful assembly
    "151": "193",  # Knowingly joining or continuing in assembly of five or more after it has been commanded to disperse
    "152": "194",  # Assaulting or obstructing public servant when suppressing riot
    "153": "195",  # Wantonly giving provocation with intent to cause riot
    "153A": "196",  # Promoting enmity between different groups
    "153B": "197",  # Imputations, assertions prejudicial to national integration
    "157": "198",  # Harbouring persons hired for an unlawful assembly
    "158": "199",  # Being hired to take part in an unlawful assembly or riot
    # ── Public nuisance (IPC 268–294) ────────────────────────────────────
    "268": "271",  # Public nuisance
    "269": "272",  # Negligent act likely to spread infection of disease dangerous to life
    "270": "273",  # Malignant act likely to spread infection of disease dangerous to life
    "271": "274",  # Disobedience to quarantine rule
    "272": "275",  # Adulteration of food or drink intended for sale
    "273": "276",  # Sale of noxious food or drink
    "274": "277",  # Adulteration of drugs
    "275": "278",  # Sale of adulterated drugs
    "276": "279",  # Sale of drug as different drug or preparation
    "277": "280",  # Fouling water of public spring or reservoir
    "278": "281",  # Making atmosphere noxious to health
    "279": "281(2)",  # Rash driving or riding on a public way
    "280": "282",  # Rash navigation of vessel
    "284": "286",  # Negligent conduct with respect to poisonous substance
    "285": "287",  # Negligent conduct with respect to fire or combustible matter
    "286": "288",  # Negligent conduct with respect to explosive substance
    "290": "292",  # Punishment for public nuisance in cases not otherwise provided for
    "292": "294",  # Sale etc. of obscene books
    "294": "296",  # Obscene acts and songs
    # ── Offences relating to religion (IPC 295–298) ─────────────────────
    "295": "298",  # Injuring or defiling place of worship with intent to insult religion
    "295A": "299",  # Deliberate and malicious acts intended to outrage religious feelings
    "296": "300",  # Disturbing religious assembly
    "297": "301",  # Trespassing on burial places
    "298": "302",  # Uttering words with deliberate intent to wound religious feelings
    # ── Offences against the human body (culpable homicide / murder) ─────
    "299": "100",  # Culpable homicide
    "300": "101",  # Murder
    "301": "102",  # Culpable homicide by causing death of person other than person intended
    "302": "103",  # Punishment for murder
    "303": "104",  # Punishment for murder by life convict
    "304": "105",  # Punishment for culpable homicide not amounting to murder
    "304A": "106(1)",  # Causing death by negligence
    "304B": "80",  # Dowry death
    # ── Suicide-related (IPC 305–309) ────────────────────────────────────
    "305": "107",  # Abetment of suicide of child or insane person
    "306": "108",  # Abetment of suicide
    "307": "109",  # Attempt to murder
    "308": "110",  # Attempt to commit culpable homicide
    "309": "224",  # Attempt to commit suicide (decriminalised — only if done to restrain public servant)
    # ── Hurt and grievous hurt (IPC 319–338) ─────────────────────────────
    "319": "114",  # Hurt
    "320": "115",  # Grievous hurt
    "321": "114(1)",  # Voluntarily causing hurt
    "322": "115(1)",  # Voluntarily causing grievous hurt
    "323": "115(2)",  # Punishment for voluntarily causing hurt
    "324": "118(1)",  # Voluntarily causing hurt by dangerous weapons or means
    "325": "117",  # Punishment for voluntarily causing grievous hurt
    "326": "118",  # Voluntarily causing grievous hurt by dangerous weapons or means
    "326A": "124",  # Voluntarily causing grievous hurt by use of acid
    "327": "118(2)",  # Voluntarily causing hurt to extort property or to constrain to illegal act
    "328": "123",  # Causing hurt by means of poison with intent to commit offence
    "329": "118(3)",  # Voluntarily causing grievous hurt to extort property
    "330": "118(4)",  # Voluntarily causing hurt to extort confession
    "331": "118(5)",  # Voluntarily causing grievous hurt to extort confession
    "332": "121",  # Voluntarily causing hurt to deter public servant from duty
    "333": "122",  # Voluntarily causing grievous hurt to deter public servant from duty
    "334": "119",  # Voluntarily causing hurt on provocation
    "335": "120",  # Voluntarily causing grievous hurt on provocation
    "336": "125(a)",  # Act endangering life or personal safety of others
    "337": "125(b)",  # Causing hurt by act endangering life or personal safety
    "338": "126",  # Causing grievous hurt by act endangering life or personal safety
    # ── Wrongful restraint and confinement (IPC 339–348) ─────────────────
    "339": "126(1)",  # Wrongful restraint
    "340": "127",  # Wrongful confinement
    "341": "126(2)",  # Punishment for wrongful restraint
    "342": "127(2)",  # Punishment for wrongful confinement
    "343": "127(3)",  # Wrongful confinement for three or more days
    "344": "127(4)",  # Wrongful confinement for ten or more days
    "346": "127(5)",  # Wrongful confinement in secret
    "347": "128",  # Wrongful confinement to extort property or constrain to illegal act
    "348": "129",  # Wrongful confinement to extort confession
    # ── Criminal force and assault (IPC 349–358) ─────────────────────────
    "349": "130",  # Force
    "350": "131",  # Criminal force
    "351": "132",  # Assault
    "352": "131(2)",  # Punishment for assault or criminal force otherwise than on grave provocation
    "353": "132(2)",  # Assault or criminal force to deter public servant from discharge of duty
    "354": "74",  # Assault or criminal force to woman with intent to outrage her modesty
    "354A": "75",  # Sexual harassment
    "354B": "76",  # Assault or use of criminal force to woman with intent to disrobe
    "354C": "77",  # Voyeurism
    "354D": "78",  # Stalking
    "355": "133",  # Assault or criminal force with intent to dishonour person
    "356": "134",  # Assault or criminal force in attempt to commit theft of property carried by person
    "357": "135",  # Assault or criminal force in attempting wrongfully to confine a person
    "358": "131(3)",  # Assault or criminal force on grave and sudden provocation
    # ── Kidnapping and abduction (IPC 359–374) ──────────────────────────
    "359": "136",  # Kidnapping
    "360": "136(1)",  # Kidnapping from India
    "361": "136(2)",  # Kidnapping from lawful guardianship
    "362": "137(1)",  # Abduction
    "363": "137",  # Punishment for kidnapping
    "363A": "141",  # Kidnapping or maiming a minor for begging
    "364": "138",  # Kidnapping or abducting in order to murder
    "364A": "140",  # Kidnapping for ransom
    "365": "138(2)",  # Kidnapping or abducting with intent secretly and wrongfully to confine person
    "366": "139",  # Kidnapping, abducting, or inducing woman to compel her marriage
    "366A": "139(2)",  # Procuration of minor girl
    "366B": "143",  # Importation of girl from foreign country
    "367": "142",  # Kidnapping or abducting in order to subject person to grievous hurt, slavery etc.
    "368": "138(3)",  # Wrongfully concealing or keeping in confinement kidnapped person
    "369": "137(2)",  # Kidnapping or abducting child under ten years with intent to steal from its person
    "370": "143(1)",  # Trafficking of person
    "371": "144(1)",  # Habitual dealing in slaves
    "372": "145",  # Selling minor for purposes of prostitution
    "373": "146",  # Buying minor for purposes of prostitution
    # ── Rape and sexual offences (IPC 375–376) ──────────────────────────
    "375": "63(1)",  # Rape — definition
    "376": "63",  # Punishment for rape
    "376A": "66",  # Punishment for causing death or resulting in persistent vegetative state
    "376AB": "65(1)",  # Rape on woman under twelve years of age
    "376B": "67",  # Sexual intercourse by husband upon wife during separation
    "376C": "68",  # Sexual intercourse by person in authority
    "376D": "70",  # Gang rape
    "376DA": "70(2)",  # Gang rape on woman under sixteen
    "376DB": "70(3)",  # Gang rape on woman under twelve
    "376E": "71",  # Repeat offenders
    # ── Criminal misappropriation (IPC 403–404) ─────────────────────────
    "403": "314",  # Dishonest misappropriation of property
    "404": "315",  # Dishonest misappropriation of property possessed by deceased person
    # ── Criminal breach of trust (IPC 405–409) ──────────────────────────
    "405": "316",  # Criminal breach of trust
    "406": "316(2)",  # Punishment for criminal breach of trust
    "407": "316(3)",  # Criminal breach of trust by carrier, wharfinger or warehouse-keeper
    "408": "316(4)",  # Criminal breach of trust by clerk or servant
    "409": "316(5)",  # Criminal breach of trust by public servant or banker etc.
    # ── Theft (IPC 378–382) ──────────────────────────────────────────────
    "378": "303",  # Theft
    "379": "303(2)",  # Punishment for theft
    "380": "305",  # Theft in dwelling house
    "381": "306",  # Theft by clerk or servant of property in possession of master
    "382": "307",  # Theft after preparation made for causing death, hurt or restraint
    # ── Extortion (IPC 383–389) ──────────────────────────────────────────
    "383": "308",  # Extortion
    "384": "308(2)",  # Punishment for extortion
    "385": "308(3)",  # Putting person in fear of injury in order to commit extortion
    "386": "308(4)",  # Extortion by putting a person in fear of death or grievous hurt
    "387": "308(5)",  # Putting person in fear of death or grievous hurt in order to commit extortion
    "388": "308(6)",  # Extortion by threat of accusation of an offence
    "389": "308(7)",  # Putting person in fear of accusation of offence in order to commit extortion
    # ── Robbery and dacoity (IPC 390–402) ────────────────────────────────
    "390": "309",  # Robbery
    "391": "310",  # Dacoity
    "392": "309(2)",  # Punishment for robbery
    "393": "309(3)",  # Attempt to commit robbery
    "394": "309(4)",  # Voluntarily causing hurt in committing robbery
    "395": "310(2)",  # Punishment for dacoity
    "396": "310(3)",  # Dacoity with murder
    "397": "310(4)",  # Robbery or dacoity with attempt to cause death or grievous hurt
    "398": "310(5)",  # Attempt to commit robbery or dacoity when armed with deadly weapon
    "399": "311",  # Making preparation to commit dacoity
    "400": "312",  # Punishment for belonging to gang of dacoits
    "401": "312(2)",  # Punishment for belonging to gang of thieves
    "402": "313",  # Assembling for purpose of committing dacoity
    # ── Receiving stolen property (IPC 410–414) ──────────────────────────
    "410": "317(1)",  # Stolen property
    "411": "317",  # Dishonestly receiving stolen property
    "412": "317(2)",  # Dishonestly receiving property stolen in dacoity
    "413": "317(3)",  # Habitually dealing in stolen property
    "414": "317(4)",  # Assisting in concealment of stolen property
    # ── Cheating (IPC 415–420) ───────────────────────────────────────────
    "415": "318",  # Cheating
    "416": "318(1)",  # Cheating by personation
    "417": "318(2)",  # Punishment for cheating
    "418": "318(3)",  # Cheating with knowledge that wrongful loss may ensue to person whose interest offender is bound to protect
    "419": "319",  # Punishment for cheating by personation
    "420": "318(4)",  # Cheating and dishonestly inducing delivery of property
    # ── Fraudulent deeds and dispositions (IPC 421–424) ──────────────────
    "421": "320",  # Dishonest or fraudulent removal or concealment of property
    "422": "321",  # Dishonestly or fraudulently preventing debt being available for creditors
    "423": "322",  # Dishonest or fraudulent execution of deed of transfer containing false statement
    "424": "323",  # Dishonest or fraudulent removal or concealment of property
    # ── Mischief (IPC 425–440) ───────────────────────────────────────────
    "425": "324",  # Mischief
    "426": "324(2)",  # Punishment for mischief
    "427": "325",  # Mischief causing damage to amount of fifty rupees (now significant amount)
    "428": "325(2)",  # Mischief by killing or maiming animal of value of ten rupees
    "429": "325(3)",  # Mischief by killing or maiming cattle etc. of any value or any animal of value of fifty rupees
    "430": "326",  # Mischief by injury to works of irrigation or by wrongfully diverting water
    "431": "326(2)",  # Mischief by injury to public road, bridge, river or channel
    "432": "326(3)",  # Mischief by causing inundation or obstruction to public drainage
    "433": "327",  # Mischief by destroying or moving etc. lighthouse or sea-mark
    "434": "327(2)",  # Mischief by destroying or moving etc. landmark fixed by public authority
    "435": "328",  # Mischief by fire or explosive substance with intent to cause damage
    "436": "328(2)",  # Mischief by fire or explosive substance with intent to destroy house etc.
    "437": "328(3)",  # Mischief with intent to destroy or make unsafe a decked vessel or one of 20 tonnes burden
    "438": "328(4)",  # Punishment for the mischief described in section 437
    "440": "328(5)",  # Mischief committed after preparation made for causing death or hurt
    # ── Criminal trespass (IPC 441–462) ──────────────────────────────────
    "441": "329",  # Criminal trespass
    "442": "329(1)",  # House-trespass
    "443": "330(1)",  # Lurking house-trespass
    "444": "330(2)",  # Lurking house-trespass by night
    "445": "331",  # House-breaking
    "446": "332",  # House-breaking by night
    "447": "329(2)",  # Punishment for criminal trespass
    "448": "330",  # Punishment for house-trespass
    "449": "333(1)",  # House-trespass in order to commit offence punishable with death
    "450": "333(2)",  # House-trespass in order to commit offence punishable with imprisonment for life
    "451": "333(3)",  # House-trespass in order to commit offence punishable with imprisonment
    "452": "333",  # House-trespass after preparation for hurt, assault or wrongful restraint
    "453": "334",  # Punishment for lurking house-trespass or house-breaking
    "454": "334(2)",  # Lurking house-trespass or house-breaking in order to commit offence punishable with imprisonment
    "455": "335",  # Lurking house-trespass or house-breaking by night — punishment
    "456": "335(2)",  # Punishment for lurking house-trespass by night or house-breaking by night
    "457": "335(3)",  # Lurking house-trespass or house-breaking by night in order to commit offence punishable with imprisonment
    "458": "335(4)",  # Lurking house-trespass or house-breaking by night after preparation for hurt
    "460": "335(5)",  # All persons jointly concerned in lurking house-trespass by night or house-breaking by night punishable where death or grievous hurt caused by one of them
    "461": "335(6)",  # Dishonestly breaking open receptacle containing property
    "462": "335(7)",  # Punishment for same by night
    # ── Forgery (IPC 463–477A) ───────────────────────────────────────────
    "463": "336",  # Forgery
    "464": "337",  # Making a false document
    "465": "338",  # Punishment for forgery
    "466": "338(2)",  # Forgery of record of Court or of public register
    "467": "338(3)",  # Forgery of valuable security, will etc.
    "468": "339",  # Forgery for purpose of cheating
    "469": "339(2)",  # Forgery for purpose of harming reputation
    "470": "340(1)",  # Forged document
    "471": "340",  # Using as genuine a forged document
    "472": "341",  # Making or possessing counterfeit seal etc. with intent to commit forgery
    "473": "341(2)",  # Making or possessing counterfeit seal etc. with intent to commit forgery of valuable security
    "474": "342",  # Having possession of document described in section 466 or 467, knowing it to be forged
    "475": "343",  # Counterfeiting device or mark used for authenticating documents
    "476": "344",  # Counterfeiting device or mark used by public servant
    "477A": "345",  # Falsification of accounts
    # ── Counterfeiting currency (IPC 489A–489E) ─────────────────────────
    "489A": "179",  # Counterfeiting currency notes or bank notes
    "489B": "180",  # Using as genuine forged or counterfeit currency notes or bank notes
    "489C": "181",  # Possession of forged or counterfeit currency notes or bank notes
    "489D": "182",  # Making or possessing instruments or materials for forging or counterfeiting
    "489E": "183",  # Making or using documents resembling currency notes or bank notes
    # ── Defamation (IPC 499–502) ─────────────────────────────────────────
    "499": "356",  # Defamation
    "500": "356(2)",  # Punishment for defamation
    "501": "356(3)",  # Printing or engraving matter known to be defamatory
    "502": "356(4)",  # Sale of printed or engraved substance containing defamatory matter
    # ── Criminal intimidation (IPC 503–510) ──────────────────────────────
    "503": "351",  # Criminal intimidation
    "504": "352",  # Intentional insult with intent to provoke breach of peace
    "505": "353",  # Statements conducing to public mischief
    "506": "351(2)",  # Punishment for criminal intimidation (simple); 351(3) for death/GH/fire threats
    "507": "351(4)",  # Criminal intimidation by anonymous communication
    "508": "354",  # Act caused by inducing person to believe that he will be rendered an object of divine displeasure
    "509": "79",  # Word, gesture or act intended to insult modesty of a woman
    "510": "355",  # Misconduct in public by a drunken person
    # ── Cruelty (IPC 498A) ───────────────────────────────────────────────
    "498A": "85",  # Cruelty by husband or relatives of husband
    # ── Offences by/against public servants ──────────────────────────────
    "166": "216",  # Public servant disobeying law with intent to cause injury
    "166A": "217",  # Public servant disobeying direction under law
    "167": "218",  # Public servant framing incorrect document with intent to cause injury
    "168": "219",  # Public servant unlawfully engaging in trade
    "169": "220",  # Public servant unlawfully buying or bidding for property
    "170": "204",  # Personating a public servant
    "171": "205",  # Wearing garb or carrying token used by public servant
    "186": "221",  # Obstructing public servant in discharge of public functions
    "188": "223",  # Disobedience to order duly promulgated by public servant
    "189": "224",  # Threat of injury to public servant
    "191": "229",  # Giving false evidence
    "192": "230",  # Fabricating false evidence
    "193": "228",  # Punishment for false evidence
    "195": "232",  # Giving or fabricating false evidence with intent to procure conviction
    "196": "233",  # Using evidence known to be false
    "199": "234",  # False statement made in declaration which is by law receivable as evidence
    "200": "235",  # Using as true such declaration knowing it to be false
    "201": "236",  # Causing disappearance of evidence or giving false information to screen offender
    "204": "238",  # Destruction of document or electronic record to prevent its production as evidence
    "211": "248",  # False charge of offence made with intent to injure
    "212": "249",  # Harbouring offender
    "213": "250",  # Taking gift etc. to screen an offender from punishment
    "214": "251",  # Offering gift or restoration of property in consideration of screening offender
    "216": "252",  # Harbouring offender who has escaped or whose apprehension has been ordered
    "216A": "253",  # Penalty for harbouring robbers or dacoits
    # ── Offences against State / sedition-related ────────────────────────
    "121": "147",  # Waging or attempting to wage war against Government of India
    "121A": "148",  # Conspiracy to commit offences punishable by section 121
    "122": "149",  # Collecting arms etc. with intention of waging war against Government of India
    "123": "150",  # Concealing with intent to facilitate design to wage war
    "124": "151",  # Assaulting President, Governor etc. with intent to compel or restrain exercise of lawful power
    "124A": "152",  # Acts endangering sovereignty, unity, and integrity of India (replaces sedition)
    "125": "153",  # Waging war against any Asiatic power in alliance with the Government of India
    "130": "157",  # Aiding escape, rescuing or harbouring prisoners of war
    # ── Offences against women — additional ──────────────────────────────
    "312": "88",  # Causing miscarriage
    "313": "89",  # Causing miscarriage without woman's consent
    "314": "90",  # Death caused by act done with intent to cause miscarriage
    "315": "91",  # Act done with intent to prevent child being born alive or to cause it to die after birth
    "316": "92",  # Causing death of quick unborn child by act amounting to culpable homicide
}

# ---------------------------------------------------------------------------
# CrPC → BNSS section mapping  (Code of Criminal Procedure, 1973 →
# Bharatiya Nagarik Suraksha Sanhita, 2023)
# ---------------------------------------------------------------------------

CRPC_TO_BNSS_MAP: Final[dict[str, str]] = {
    # ── Arrest (CrPC 41–54) ──────────────────────────────────────────────
    "41": "35",  # When police may arrest without warrant
    "41A": "35(3)",  # Notice of appearance before police officer
    "42": "36",  # Arrest on refusal to give name and residence
    "43": "37",  # Arrest by private person
    "44": "38",  # Arrest by Magistrate
    "45": "39",  # Protection of members of Armed Forces from arrest
    "46": "40",  # How arrests are made
    "47": "41",  # Search of place entered by person sought to be arrested
    "48": "42",  # Pursuit of offenders into other jurisdictions
    "49": "43",  # No unnecessary restraint
    "50": "44",  # Person arrested to be informed of grounds of arrest
    "51": "45",  # Search of arrested person
    "52": "46",  # Seizure of offensive weapons
    "53": "47",  # Examination of person arrested
    "54": "48",  # Examination of arrested person by medical practitioner
    # ── Preventive action / security proceedings ─────────────────────────
    "91": "105",  # Summons to produce document or thing
    "97": "104",  # Search for persons wrongfully confined
    "100": "108",  # Persons in charge of closed place to allow search
    "102": "111",  # Power of police officer to seize certain property
    "107": "121",  # Security for keeping the peace
    "108": "122",  # Security for good behaviour from persons disseminating seditious matter
    "110": "124",  # Security for good behaviour from habitual offenders
    # ── Maintenance (CrPC 125–129) ───────────────────────────────────────
    "125": "144",  # Order for maintenance of wives, children and parents
    "126": "145",  # Procedure for maintenance
    "127": "146",  # Alteration in allowance
    "128": "147",  # Enforcement of order of maintenance
    "129": "148",  # Implementation of order of maintenance
    # ── Nuisance / urgent orders (CrPC 133–148) ─────────────────────────
    "133": "152",  # Conditional order for removal of nuisance
    "144": "163",  # Power to issue order in urgent cases of nuisance or apprehended danger
    "145": "165",  # Procedure where dispute concerning land or water is likely to cause breach of peace
    "146": "166",  # Power to attach subject of dispute
    "149": "169",  # Police to prevent cognizable offences
    # ── Information to police / FIR (CrPC 153–173) ──────────────────────
    "153": "172",  # Information as to non-cognizable cases and investigation of such cases
    "154": "173",  # Information in cognizable cases (FIR)
    "155": "174",  # Information as to non-cognizable cases
    "156": "175",  # Police officer's power to investigate cognizable cases
    "157": "176",  # Procedure for investigation
    "158": "177",  # Report how investigation is to be made
    "159": "178",  # Power to hold investigation or preliminary inquiry
    "160": "179",  # Police officer's power to require attendance of witnesses
    "161": "180",  # Examination of witnesses by police
    "162": "181",  # Statements to police not to be signed; use of statements in evidence
    "163": "182",  # No inducement to be offered
    "164": "183",  # Recording of confessions and statements
    "164A": "184",  # Medical examination of rape victim
    "165": "185",  # Search by police officer
    "166": "186",  # When officer in charge of police station may require another to issue search warrant
    "167": "187",  # Procedure when investigation cannot be completed in 24 hours
    "168": "188",  # Report of investigation by subordinate police officer
    "169": "189",  # Release of accused when evidence is deficient
    "170": "190",  # Cases to be sent to Magistrate when evidence is sufficient
    "171": "191",  # Complainant and witnesses not to be required to accompany police officer
    "172": "192",  # Diary of proceedings in investigation
    "173": "193",  # Report of police officer on completion of investigation (chargesheet)
    # ── Cognizance and commencement of proceedings (CrPC 190–199) ────────
    "190": "210",  # Cognizance of offences by Magistrates
    "191": "211",  # Transfer on application of accused
    "192": "212",  # Making over cases to Magistrates
    "193": "213",  # Cognizance of offences by Courts of Session
    "197": "217",  # Prosecution of Judges and public servants (sanction for prosecution)
    "199": "219",  # Prosecution for defamation
    "200": "220",  # Examination of complainant
    "203": "227",  # Dismissal of complaint
    "204": "228",  # Issue of process
    # ── Trial provisions (CrPC 207–233) ──────────────────────────────────
    "207": "231",  # Supply of copy of police report and other documents to accused
    "209": "233",  # Commitment of case to Court of Session
    "211": "235",  # Contents of charge
    "216": "240",  # Court may alter charge
    "225": "258",  # Previous acquittal or conviction
    "226": "259",  # Opening case for prosecution
    "227": "260",  # Discharge
    "228": "261",  # Framing of charge
    "230": "263",  # Date for prosecution evidence
    "231": "264",  # Evidence for prosecution
    "232": "265",  # Acquittal
    "233": "266",  # Entering upon defence
    "235": "268",  # Judgment of acquittal or conviction
    "239": "272",  # When accused shall be discharged (warrant cases on complaint)
    "240": "273",  # Framing of charge in warrant cases on complaint
    "241": "274",  # Conviction on plea of guilty
    "242": "275",  # Evidence for prosecution
    "243": "276",  # Evidence for defence
    "244": "277",  # Procedure when accused is not discharged
    "245": "278",  # When accused shall be acquitted (summons trial)
    "246": "279",  # Procedure where accused is not acquitted
    "247": "280",  # Non-appearance or death of complainant
    "248": "281",  # Acquittal or conviction (summons case)
    "250": "283",  # Compensation for accusation without reasonable cause
    "251": "284",  # Substance of accusation to be stated (summons case)
    "252": "285",  # Conviction on plea of guilty (summons case)
    "253": "285",  # Conviction on plea of guilty in petty cases (merged)
    # ── Examination of accused ───────────────────────────────────────────
    "313": "351",  # Power to examine the accused
    # ── Miscellaneous trial / procedure ──────────────────────────────────
    "319": "366",  # Power to proceed against other persons appearing to be guilty of offence
    "321": "368",  # Withdrawal from prosecution
    "326": "373",  # Conviction or commitment on evidence partly recorded by one Presiding Officer
    "327": "374",  # Court to be open
    "328": "375",  # Procedure in case of accused being lunatic
    "329": "376",  # Procedure in case of person of unsound mind tried before Court
    "330": "377",  # Release of lunatic pending investigation or trial
    "340": "387",  # Procedure in certain cases of contempt
    "341": "388",  # Appeal in contempt cases
    "342": "389",  # Power to order costs
    "343": "390",  # Procedure of Magistrate not competent to take cognizance of the case
    "344": "391",  # Power to postpone or adjourn proceedings
    "345": "392",  # Procedure to deal with certain offences committed before Court (contempt)
    # ── Judgment and sentence (CrPC 353–361) ─────────────────────────────
    "353": "391",  # Judgment
    "354": "392",  # Language of judgments
    "355": "393",  # Metropolitan Magistrate's judgment
    "357": "395",  # Order to pay compensation
    "357A": "396",  # Victim compensation scheme
    "360": "399",  # Order to release on probation of good conduct or after admonition
    "361": "400",  # Special reasons to be recorded in certain cases
    # ── Appeals (CrPC 372–394) ───────────────────────────────────────────
    "372": "410",  # No appeal to lie unless otherwise provided
    "374": "413",  # Appeals from convictions
    "375": "414",  # No appeal in certain cases if accused pleads guilty
    "376": "415",  # No appeal in petty cases
    "377": "416",  # Appeal by State Government against sentence
    "378": "417",  # Appeal in case of acquittal
    "379": "418",  # Appeal against conviction by HC in certain cases
    "380": "419",  # Special right of appeal in certain cases
    "386": "424",  # Powers of Appellate Court
    "389": "427",  # Suspension of sentence pending appeal; release of appellant on bail
    "390": "428",  # Arrest of accused in appeal from acquittal
    # ── Reference and revision (CrPC 395–407) ───────────────────────────
    "395": "434",  # Reference to High Court
    "397": "436",  # Calling for records to examine the correctness of proceedings (revision)
    "399": "438",  # Sessions Judge's powers of revision
    "401": "440",  # High Court's powers of revision
    "402": "441",  # Power of HC to withdraw or transfer cases
    # ── Bail (CrPC 436–440) ─────────────────────────────────────────────
    "436": "478",  # In what cases bail to be taken
    "436A": "479",  # Maximum period for which an undertrial prisoner can be detained
    "437": "480",  # When bail may be taken in case of non-bailable offence
    "438": "482",  # Direction for grant of bail (anticipatory bail)
    "439": "483",  # Special powers of High Court or Court of Session regarding bail
    "440": "484",  # Amount of bond and reduction thereof
    # ── Execution / Jail / Sentence (CrPC 413–435) ──────────────────────
    "413": "452",  # Who may issue warrant
    "416": "455",  # Postponement of execution of sentence of death in case of appeal
    "427": "466",  # Concurrent sentences
    "428": "467",  # Period of detention undergone by accused to be set off against sentence
    # ── Transfer of cases ────────────────────────────────────────────────
    "406": "446",  # Power of Supreme Court to transfer cases and appeals
    "407": "447",  # Power of High Court to transfer cases and appeals
    "408": "448",  # Power of Sessions Judge to transfer cases and appeals
    # ── Miscellaneous ────────────────────────────────────────────────────
    "451": "497",  # Order for custody and disposal of property pending trial
    "457": "503",  # Procedure by police upon seizure of property
    "460": "506",  # Irregularities which do not vitiate proceedings
    "461": "507",  # Irregularities which vitiate proceedings
    "464": "510",  # Effect of omission to frame or absence of or error in charge
    "465": "511",  # Finding or sentence when reversible by reason of error or irregularity
    "468": "514",  # Bar to taking cognizance after lapse of period of limitation
    "469": "515",  # Commencement of period of limitation
    "470": "516",  # Exclusion of time in certain cases
    "471": "517",  # Exclusion of date on which Court is closed
    "472": "518",  # Continuing offence
    "473": "519",  # Extension of period of limitation in certain cases
    # ── Inherent powers ──────────────────────────────────────────────────
    "482": "528",  # Saving of inherent powers of High Court
}

# ---------------------------------------------------------------------------
# Indian Evidence Act, 1872 → BSA mapping  (Bharatiya Sakshya Adhiniyam, 2023)
# ---------------------------------------------------------------------------

EVIDENCE_TO_BSA_MAP: Final[dict[str, str]] = {
    # ── Preliminary / Definitions (IEA 1–4) ──────────────────────────────
    "3": "2",  # Interpretation clause / definitions
    "4": "3",  # "May presume" / "shall presume" / "conclusive proof"
    # ── Relevancy of facts (IEA 5–55) ────────────────────────────────────
    "5": "4",  # Evidence may be given of facts in issue and relevant facts
    "6": "5",  # Relevancy of facts forming part of same transaction (res gestae)
    "7": "6",  # Facts which are occasion, cause, or effect of relevant facts
    "8": "7",  # Motive, preparation and previous or subsequent conduct
    "9": "8",  # Facts necessary to explain or introduce relevant facts
    "10": "9",  # Things said or done by conspirator in reference to common design
    "11": "10",  # When facts not otherwise relevant become relevant
    "14": "13",  # Facts showing existence of state of mind or body or bodily feeling
    "15": "14",  # Facts bearing on question whether act was accidental or intentional
    "17": "16",  # Admission defined
    "21": "20",  # Proof of admissions against persons making them
    "24": "23",  # Confession caused by inducement, threat or promise
    "25": "24",  # Confession to police officer not to be proved
    "27": "25",  # How much information received from accused may be proved
    "32": "26",  # Cases in which statement of relevant fact by person who is dead (dying declaration)
    "35": "33",  # Relevancy of entry in public record made in performance of duty
    "45": "39",  # Opinion of experts
    "47": "41",  # Opinion as to handwriting when relevant
    # ── Electronic records (IEA 56–65B) ──────────────────────────────────
    "56": "50",  # Fact judicially noticeable need not be proved
    "57": "51",  # Facts of which Court must take judicial notice
    "58": "52",  # Facts admitted need not be proved
    "59": "53",  # Proof of facts by oral evidence
    "60": "54",  # Oral evidence must be direct
    "61": "55",  # Proof of contents of documents
    "62": "56",  # Primary evidence
    "63": "57",  # Secondary evidence
    "64": "58",  # Proof of documents by primary evidence
    "65": "59",  # Cases in which secondary evidence relating to documents may be given
    "65A": "60",  # Special provisions as to evidence relating to electronic record
    "65B": "63",  # Admissibility of electronic records
    # ── Public and private documents (IEA 73–80) ─────────────────────────
    "73": "67",  # Comparison of signature, writing or seal with others admitted or proved
    "74": "68",  # Public documents
    "75": "69",  # Private documents
    "76": "70",  # Certified copies of public documents
    "77": "71",  # Proof of documents by production of certified copies
    "78": "72",  # Proof of other official documents
    "79": "73",  # Presumption as to genuineness of certified copies
    "80": "74",  # Presumption as to documents produced as record of evidence
    "81": "75",  # Presumption as to Gazettes, newspapers, etc.
    "82": "76",  # Presumption as to document admissible in England without proof of seal or signature
    "85": "79",  # Presumption as to powers of attorney
    "90": "84",  # Presumption as to documents thirty years old
    # ── Burden of proof (IEA 101–114) ────────────────────────────────────
    "101": "95",  # Burden of proof
    "102": "96",  # On whom burden of proof lies
    "103": "97",  # Burden of proof as to particular fact
    "104": "98",  # Burden of proving fact to be proved to make evidence admissible
    "105": "99",  # Burden of proving that case of accused comes within exceptions
    "106": "100",  # Burden of proving fact especially within knowledge
    "107": "101",  # Burden of proving death of person known to have been alive within thirty years
    "108": "102",  # Burden of proving that person is alive who has not been heard of for seven years
    "111": "104",  # Proof of age of person over whom age is in question
    "112": "105",  # Birth during marriage conclusive proof of legitimacy
    "113": "106",  # Proof of cession of territory
    "113A": "118",  # Presumption as to abetment of suicide by married woman
    "113B": "119",  # Presumption as to dowry death
    "114": "120",  # Court may presume existence of certain facts
    # ── Estoppel (IEA 115–117) ───────────────────────────────────────────
    "115": "108",  # Estoppel
    "116": "109",  # Estoppel of tenant and of licensee of person in possession
    "117": "110(1)",  # Estoppel of acceptor of bill of exchange
    # ── Witnesses (IEA 118–134) ──────────────────────────────────────────
    "118": "110",  # Who may testify
    "119": "111",  # Dumb witnesses
    "120": "112",  # Parties to civil suit and their wives or husbands — competence and compellability
    "121": "113",  # Judges and Magistrates
    "122": "114",  # Communications during marriage
    "123": "115",  # Evidence as to affairs of State
    "131": "121",  # Production of documents which another person could refuse to produce
    "132": "122",  # Witness not excused from answering on ground that answer will criminate
    "133": "123",  # Accomplice
    "134": "124",  # Number of witnesses
    # ── Examination of witnesses (IEA 135–166) ───────────────────────────
    "136": "126",  # Judge to decide as to admissibility of evidence
    "137": "127",  # Examination-in-chief, cross-examination and re-examination
    "138": "128",  # Order of examinations
    "139": "129",  # Cross-examination of person called to produce a document
    "140": "130",  # Witnesses to character
    "145": "137",  # Cross-examination as to previous statements in writing
    "154": "146",  # Question by party to his own witness (hostile witness)
    "155": "147",  # Impeaching credit of witness
    "156": "148",  # Questions tending to corroborate evidence of relevant fact
    "157": "149",  # Former statements of witness may be proved to corroborate later testimony
    "158": "150",  # What matters may be proved in connection with proved statement relevant under section 32 or 33
    "159": "151",  # Refreshing memory
    "160": "152",  # Testimony to facts stated in document mentioned in section 159
    "161": "153",  # Right of adverse party as to writing used to refresh memory
    "162": "154",  # Production of documents
    "163": "155",  # Giving as evidence of document called for and produced on notice
}

# ---------------------------------------------------------------------------
# Hindi Legal Terminology Glossary
# Maps common English legal terms to Hindi equivalents (Devanagari script).
# Used for Hindi language support in search, agents, and UI.
# ---------------------------------------------------------------------------

HINDI_LEGAL_GLOSSARY: Final[dict[str, str]] = {
    # ── Core legal terms ────────────────────────────────────────────────────
    "petition": "याचिका",
    "bail": "जमानत",
    "judgment": "निर्णय",
    "appeal": "अपील",
    "accused": "अभियुक्त",
    "complainant": "शिकायतकर्ता",
    "advocate": "अधिवक्ता",
    "court": "न्यायालय",
    "evidence": "साक्ष्य",
    "witness": "गवाह",
    "prosecution": "अभियोजन",
    "defense": "बचाव",
    "sentence": "सजा",
    "acquittal": "बरी",
    "conviction": "दोषसिद्धि",
    "FIR": "प्रथम सूचना रिपोर्ट",
    "chargesheet": "आरोप पत्र",
    "custody": "हिरासत",
    "remand": "रिमांड",
    "hearing": "सुनवाई",
    "order": "आदेश",
    "decree": "डिक्री",
    "plaintiff": "वादी",
    "defendant": "प्रतिवादी",
    "writ": "रिट",
    "statute": "विधि",
    "law": "कानून",
    "justice": "न्याय",
    "judge": "न्यायाधीश",
    "lawyer": "वकील",
    # ── Writ types ──────────────────────────────────────────────────────────
    "habeas corpus": "बंदी प्रत्यक्षीकरण",
    "mandamus": "परमादेश",
    "certiorari": "उत्प्रेषण",
    "prohibition": "प्रतिषेध",
    "quo warranto": "अधिकार पृच्छा",
    # ── Procedural terms ────────────────────────────────────────────────────
    "anticipatory bail": "अग्रिम जमानत",
    "cognizable offence": "संज्ञेय अपराध",
    "non-cognizable offence": "असंज्ञेय अपराध",
    "bailable offence": "जमानतीय अपराध",
    "non-bailable offence": "गैर-जमानतीय अपराध",
    "summons": "समन",
    "warrant": "वारंट",
    "affidavit": "शपथ पत्र",
    "adjournment": "स्थगन",
    "stay order": "स्थगन आदेश",
    "interim order": "अंतरिम आदेश",
    "injunction": "निषेधाज्ञा",
    "limitation": "परिसीमा",
    "jurisdiction": "अधिकार क्षेत्र",
    "quash": "रद्द करना",
    "appeal dismissed": "अपील खारिज",
    "appeal allowed": "अपील स्वीकार",
    # ── Court hierarchy ─────────────────────────────────────────────────────
    "Supreme Court": "सर्वोच्च न्यायालय",
    "High Court": "उच्च न्यायालय",
    "District Court": "जिला न्यायालय",
    "Sessions Court": "सत्र न्यायालय",
    "Magistrate Court": "मजिस्ट्रेट न्यायालय",
    "Tribunal": "अधिकरण",
    # ── Parties and roles ───────────────────────────────────────────────────
    "appellant": "अपीलकर्ता",
    "respondent": "प्रत्यर्थी",
    "petitioner": "याचिकाकर्ता",
    "applicant": "आवेदक",
    "surety": "जमानतदार",
    "public prosecutor": "लोक अभियोजक",
    "amicus curiae": "न्यायमित्र",
    # ── Substantive law terms ───────────────────────────────────────────────
    "murder": "हत्या",
    "theft": "चोरी",
    "robbery": "लूट",
    "dacoity": "डकैती",
    "forgery": "जालसाजी",
    "cheating": "धोखाधड़ी",
    "defamation": "मानहानि",
    "dowry": "दहेज",
    "cruelty": "क्रूरता",
    "negligence": "लापरवाही",
    "culpable homicide": "गैर-इरादतन हत्या",
    "grievous hurt": "गंभीर चोट",
    "kidnapping": "अपहरण",
    "extortion": "उगाही",
    "mischief": "रिष्टि",
    "trespass": "अतिचार",
    "abetment": "दुष्प्रेरण",
    "conspiracy": "षड्यंत्र",
    # ── Legal principles ────────────────────────────────────────────────────
    "ratio decidendi": "निर्णय का आधार",
    "obiter dictum": "प्रासंगिक टिप्पणी",
    "stare decisis": "पूर्व निर्णयानुसरण",
    "precedent": "पूर्व निर्णय",
    "natural justice": "प्राकृतिक न्याय",
    "due process": "उचित प्रक्रिया",
    "fundamental rights": "मौलिक अधिकार",
    "directive principles": "नीति निर्देशक तत्व",
    "ultra vires": "अधिकातीत",
    "res judicata": "पूर्व न्याय",
    "locus standi": "वाद योग्यता",
}
