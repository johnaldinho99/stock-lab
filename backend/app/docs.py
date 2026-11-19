"""Long-form explanations shown under "Så fungerar den". Trusted HTML (authored here)."""

from __future__ import annotations


def S(title: str, html: str) -> dict:
    return {"title": title, "html": html.strip()}


GENERAL = [
    S("Så räknar Aktielabbet", """
<p>Alla strategier simuleras månadsvis. Vid varje månadsskifte räknas strategins signal ut på
<b>stängningskursen den dagen</b>, och portföljen antas handlas till samma kurs. Avkastningen för
nästa månad tillfaller sedan de nya innehaven. Mellan ombalanseringarna får vikterna glida med
marknaden – precis som i en riktig portfölj.</p>
<ul>
<li><b>Utdelningar</b> återinvesteras (justerade kurser från Yahoo Finance).</li>
<li><b>Transaktionskostnader</b> dras på det handlade beloppet vid varje ombalansering (standard 0,10 %).</li>
<li><b>Kontanter</b> ger amerikansk statsskuldväxelränta (13 veckor, ^IRX).</li>
<li><b>Valuta:</b> allt i USD. OMXS30 räknas om från SEK med USD/SEK-kursen.</li>
<li><b>Skatt</b> räknas inte med (t.ex. ISK-schablon eller kapitalvinstskatt).</li>
</ul>"""),
    S("Data och dess begränsningar", """
<p><b>Kurser:</b> Yahoo Finance via yfinance (dagliga, från år 2000). <b>Nyckeltal:</b> SEC EDGAR
(XBRL), de officiella rapporter amerikanska bolag lämnar in. Varje siffra har ett <i>inlämningsdatum</i>,
och backtesten använder bara siffror som var publicerade vid respektive tidpunkt – inget fusk med
framtida information. XBRL-data finns för stora bolag från 2009 och för alla från 2011, därför startar
Magic Formula-strategierna 2010–2011.</p>
<p><b>Överlevnadsbias (survivorship bias):</b> Universumet är <i>dagens</i> ~900 bolag i S&amp;P 500 och
S&amp;P MidCap 400. För att minska problemet blir en aktie <b>valbar först från det datum den kom in i
indexet</b> (S&amp;P 500: Wikipedias inträdesdatum; S&amp;P 400: ändringsloggen från 2012 – bolag med okänt
datum räknas som valbara från 2012). Utan det skulle t.ex. en momentumstrategi kunna "köpa" NVIDIA 2003,
långt innan någon visste att det skulle bli ett jättebolag – och ML-modellen lärde sig först just det
fusket. Men bolag som gick i konkurs, köptes upp eller åkte ur indexen saknas fortfarande, så alla
aktiestrategier ser något bättre ut historiskt än de hade gjort i verkligheten. Före 2012 är universumet
mindre (~200–280 bolag). Jämför därför aktiestrategier främst mot
<b>"Lika vikt – hela universumet"</b>, som har exakt samma bias. Skillnaden mot den är ett ärligare
mått på strategins egen förmåga än skillnaden mot S&amp;P 500.</p>
<p><b>OMXS30</b> är ett prisindex utan utdelningar (ca 3–4 % per år lägre än totalavkastning) –
det finns tyvärr ingen gratis daglig serie med utdelningar.</p>"""),
    S("Konfidensintervall – hur de räknas", """
<p>Under <i>Framtid &amp; osäkerhet</i> används <b>block-bootstrap</b>: strategins historiska
månadsavkastningar delas upp i block om 12 sammanhängande månader, och tusentals möjliga framtider
byggs genom att dra block slumpmässigt och lägga dem efter varandra. Blocken bevarar krascher,
trender och perioder av hög volatilitet. Strategin och S&amp;P 500 dras alltid med <i>samma månader</i>,
så att samvariationen mellan dem behålls när vi frågar "hur ofta slår den index?".</p>
<ul>
<li><b>Solfjädern</b> visar vart 4 000 simulerade framtider tar 1 dollar: mitten (median), det
mittersta 50 %-bandet och 90 %-bandet.</li>
<li><b>Intervall för historisk avkastning</b> svarar på "hur säker kan vi vara på att strategins
historiska avkastning inte var tur?". Om 95 %-intervallet för försprånget mot S&amp;P 500 innehåller
noll kan resultatet mycket väl vara slump.</li>
<li><b>Köp idag</b>: fördelningen för alla historiska 12-månadersperioder – vad ett köp en slumpmässig
månad gav året efter.</li>
</ul>
<p><b>Viktigt:</b> Alla intervall bygger på antagandet att framtiden liknar backtestperioden statistiskt.
Det är det svagaste antagandet av alla – marknader förändras, strategier blir kända och arbitreras bort,
och 15 år är en kort period. Se intervallen som en <i>nedre gräns för osäkerheten</i>, inte som löften.</p>"""),
    S("Inte investeringsrådgivning", """
<p>Aktielabbet är ett verktyg för lärande och analys. Historisk avkastning är ingen garanti för
framtida avkastning, och en backtest är alltid optimistisk: den vet inte om sina egna
datafel, den har ingen psykologi och den har valts ut bland många idéer (data mining). Gör din
egen bedömning – och tänk på att enkla, billiga indexfonder är svåra att slå över tid.</p>"""),
]


DOCS: dict[str, list[dict]] = {}

DOCS["ew_universe"] = [
    S("Idén i korthet", """
<p>Köp <b>alla</b> aktier i universumet (~900 st.) med exakt lika stor vikt, och återställ vikterna
regelbundet. Det är ingen strategi man väljer för att den är smart – den finns här som
<b>måttstock</b> för aktiestrategierna.</p>"""),
    S("Varför den behövs", """
<p>Universumet består av dagens indexbolag, alltså vinnarna. Det ger alla aktiestrategier en
konstgjord medvind (överlevnadsbias). "Lika vikt" har exakt samma medvind. Om Magic Formula slår
S&amp;P 500 med 4 % per år men "Lika vikt" slår S&amp;P 500 med 3 % är strategins egen förmåga
bara ungefär 1 % – resten är bias och den så kallade <i>storlekseffekten</i>.</p>
<p>Lika vikt har dessutom historiskt slagit börsvärdesviktade index på lång sikt eftersom den
har mer i mindre bolag och automatiskt säljer det som stigit och köper det som fallit
(ombalansering). Under perioder när ett fåtal jättebolag driver marknaden (som 2015–2024) har
den däremot halkat efter.</p>"""),
    S("Formeln", """
<div class="formula">vikt<sub>i</sub> = 1 / N &nbsp;&nbsp; för alla aktier i med minst 12 månaders kurshistorik</div>"""),
]

DOCS["sixty_forty"] = [
    S("Idén i korthet", """
<p>Den klassiska blandportföljen: <b>60 % aktier</b> (S&amp;P 500) och <b>40 % statsobligationer</b>
(7–10 år). Varje månad återställs fördelningen. Aktierna står för tillväxten, obligationerna för
stabiliteten – de har historiskt ofta rört sig åt olika håll när det verkligen gällt.</p>"""),
    S("Reglerna steg för steg", """
<ol>
<li>Investera 60 % i SPY (S&amp;P 500) och 40 % i IEF (amerikanska statsobligationer 7–10 år).</li>
<li>Vid varje månadsskifte: sälj det som vuxit över sin målvikt och köp det som krympt.</li>
<li>Upprepa. Ingen prognos, ingen tajming.</li>
</ol>"""),
    S("Varför skulle det fungera?", """
<p>Idén bygger på Harry Markowitz portföljteori (1952): genom att kombinera tillgångar som inte rör
sig exakt lika får man bättre avkastning per enhet risk än med någon av dem ensam.
Ombalanseringen tvingar dig att sälja dyrt och köpa billigt – och ger en liten
"ombalanseringsbonus" när tillgångarna svänger.</p>"""),
    S("Risker och svagheter", """
<ul>
<li><b>2022</b> visade svagheten: när inflationen steg föll både aktier och obligationer kraftigt
samtidigt, och 60/40 hade ett av sina sämsta år på decennier.</li>
<li>Lägre förväntad avkastning än 100 % aktier på lång sikt.</li>
<li>Obligationernas skydd beror på att räntorna kan sjunka i en kris – från låga räntenivåer är
utrymmet mindre.</li>
</ul>"""),
    S("Så är den implementerad här", """
<p>SPY och IEF med utdelningar återinvesterade. Andelen aktier kan ändras (40/60/80 %). Startar
när IEF finns (2002).</p>"""),
]

DOCS["trend_sma"] = [
    S("Idén i korthet", """
<p>Äg aktiemarknaden när den är i en <b>upptrend</b>, och kliv av till kontanter när den inte är det.
Trenden mäts med det enklaste möjliga verktyget: ligger priset över eller under sitt
<b>10-månaders glidande medelvärde</b>? Målet är inte högre avkastning utan att slippa de värsta
krascherna.</p>"""),
    S("Reglerna steg för steg", """
<ol>
<li>Sista handelsdagen varje månad: räkna ut medelvärdet av de senaste 10 månadsslutskurserna för S&amp;P 500.</li>
<li>Om kursen är <b>över</b> medelvärdet: äg S&amp;P 500 (SPY).</li>
<li>Om kursen är <b>under</b>: sälj allt och placera i statsskuldväxlar (eller obligationer).</li>
<li>Gör ingenting mellan månadsskiftena.</li>
</ol>"""),
    S("Formeln", """
<div class="formula">SMA<sub>10</sub>(t) = (P<sub>t</sub> + P<sub>t−1</sub> + … + P<sub>t−9</sub>) / 10<br>
Signal = P<sub>t</sub> &gt; SMA<sub>10</sub>(t) ? Aktier : Kontanter</div>"""),
    S("Vad säger forskningen?", """
<p>Mebane Faber publicerade regeln 2007 (<i>A Quantitative Approach to Tactical Asset Allocation</i>)
och visade att den över 100 år gav ungefär aktiemarknadens avkastning med betydligt lägre
volatilitet och mycket mindre maximala ras. Trendföljning finns i alla tillgångsslag och är
en av de mest väldokumenterade marknadseffekterna (se även "Time Series Momentum", Moskowitz,
Ooi &amp; Pedersen 2012). Den kom ut ur aktier tidigt under finanskrisen 2008.</p>"""),
    S("Varför skulle det fungera?", """
<p>Stora björnmarknader sker sällan över en natt – de pågår i månader medan ekonomin försämras.
Investerare reagerar trögt på ny information och trender tenderar därför att fortsätta en tid.
Trendregeln låter dig missa en del av de långa nedgångarna.</p>"""),
    S("Risker och svagheter", """
<ul>
<li><b>Falska signaler</b> ("whipsaw"): i sidledes marknader säljer du efter en nedgång och köper
tillbaka högre. Det kostar avkastning, ofta flera år i rad.</li>
<li><b>Snabba krascher</b> som coronakraschen 2020 (−34 % på en månad) hinner inte fångas med
månadsdata – och återhämtningen missas delvis.</li>
<li>I långa, stabila tjurmarknader släpar den nästan alltid efter köp-och-behåll.</li>
<li>Skattemässigt ofördelaktigt utanför ISK/KF eftersom vinster realiseras.</li>
</ul>"""),
    S("Så är den implementerad här", """
<p>SPY mot sitt 6/10/12-månaders medelvärde (10 som standard, som Faber). Vid sälj placeras pengarna
i statsskuldväxlar eller i statsobligationer (IEF).</p>"""),
]

DOCS["dual_momentum"] = [
    S("Idén i korthet", """
<p>Gary Antonaccis <b>Global Equities Momentum</b> kombinerar två sorters momentum:</p>
<ul>
<li><b>Relativ momentum</b> – välj den aktiemarknad (USA eller resten av världen) som gått bäst
senaste året.</li>
<li><b>Absolut momentum</b> – äg den bara om den slagit räntan på statsskuldväxlar. Annars:
obligationer.</li>
</ul>
<p>Portföljen har alltså alltid 100 % i <i>en</i> tillgång.</p>"""),
    S("Reglerna steg för steg", """
<ol>
<li>Varje månadsskifte: räkna 12-månadersavkastningen för SPY (USA), EFA (Europa, Japan m.fl.) och statsskuldväxlar.</li>
<li>Är vinnaren av SPY/EFA bättre än statsskuldväxlarna? Investera allt i vinnaren.</li>
<li>Annars: investera allt i amerikanska obligationer (AGG).</li>
</ol>"""),
    S("Formeln", """
<div class="formula">R<sub>12</sub>(X) = P<sub>t</sub>(X) / P<sub>t−12</sub>(X) − 1<br>
Vinnare = argmax(R<sub>12</sub>(SPY), R<sub>12</sub>(EFA))<br>
Innehav = R<sub>12</sub>(Vinnare) &gt; R<sub>12</sub>(T-bills) ? Vinnare : AGG</div>"""),
    S("Vad säger forskningen?", """
<p>Antonacci beskriver strategin i boken <i>Dual Momentum Investing</i> (2014) och visade att den
historiskt (från 1970-talet) gav högre avkastning än världsindex med ungefär halverade maximala ras.
Den bygger på samma momentumeffekt som Jegadeesh &amp; Titman dokumenterade för enskilda aktier,
men tillämpad på hela marknader.</p>"""),
    S("Risker och svagheter", """
<ul>
<li>Sedan boken kom har USA nästan alltid vunnit, så strategin har mest varit S&amp;P 500 med
några dyra hopp till obligationer (t.ex. 2016, 2018–2019 och 2022–2023).</li>
<li>Koncentrerad: alla ägg i en korg. När signalen ändras vid fel tillfälle kostar det mycket.</li>
<li>Obligationer som skydd fungerade dåligt 2022.</li>
</ul>"""),
    S("Så är den implementerad här", """
<p>SPY, EFA och AGG som ETF:er med utdelningar, 12 månaders mätperiod (6 kan väljas).
Statsskuldväxelräntan kommer från ^IRX. Startar 2004 när alla ETF:er har 12 månaders historik.</p>"""),
]

DOCS["momentum"] = [
    S("Idén i korthet", """
<p>Aktier som gått bäst det senaste året tenderar att fortsätta gå bra de närmaste månaderna.
Strategin köper de <b>30 aktier</b> med högst avkastning de senaste 12 månaderna – men
<b>hoppar över den senaste månaden</b>, eftersom aktier på mycket kort sikt i stället tenderar att
studsa tillbaka.</p>"""),
    S("Reglerna steg för steg", """
<ol>
<li>Varje månadsskifte: räkna varje akties avkastning från 12 månader sedan till 1 månad sedan.</li>
<li>Rangordna alla ~900 aktier.</li>
<li>Köp de 30 bästa med lika vikt, sälj de som ramlat ur topplistan.</li>
</ol>"""),
    S("Formeln", """
<div class="formula">Momentum<sub>12−1</sub> = P<sub>t−1</sub> / P<sub>t−12</sub> − 1</div>"""),
    S("Vad säger forskningen?", """
<p>Jegadeesh &amp; Titman (1993) visade att en portfölj av tidigare vinnare slog tidigare förlorare
med omkring 1 % per månad i amerikanska data 1965–1989. Effekten har sedan hittats i nästan alla
länder och tillgångsslag och ingår i Carharts fyrfaktormodell (1997). Det är en av de mest robusta –
och mest omdiskuterade – anomalierna eftersom den strider mot effektiva marknader.</p>"""),
    S("Varför skulle det fungera?", """
<ul>
<li><b>Underreaktion:</b> investerare tar till sig goda nyheter långsamt, så kursen anpassar sig gradvis.</li>
<li><b>Flockbeteende</b> förstärker trender en tid.</li>
<li><b>Riskpremie:</b> momentum kraschar ibland våldsamt, och den risken kräver betalt.</li>
</ul>"""),
    S("Risker och svagheter", """
<ul>
<li><b>Momentumkrascher:</b> när marknaden vänder upp kraftigt efter en baisse (t.ex. våren 2009)
rusar de hårdast nedtryckta aktierna och momentumportföljen förlorar stort (Daniel &amp; Moskowitz 2016).</li>
<li>Hög omsättning – ofta 300–600 % per år – ger höga kostnader och kortsiktiga vinster.</li>
<li>Portföljen blir ofta koncentrerad i en sektor (t.ex. tech eller energi).</li>
</ul>"""),
    S("Så är den implementerad här", """
<p>12–1-momentum på justerade kurser för alla ~900 aktier, 10–100 aktier, ombalansering varje
månad eller kvartal. Ingen sektorbegränsning.</p>"""),
]

DOCS["low_vol"] = [
    S("Idén i korthet", """
<p>Enligt klassisk teori ska högre risk ge högre avkastning. I praktiken har de <b>lugnaste
aktierna</b> gett ungefär lika hög avkastning som marknaden – men med klart mindre svängningar.
Strategin köper de 50 aktier som svängt minst det senaste året.</p>"""),
    S("Reglerna steg för steg", """
<ol>
<li>Räkna varje akties volatilitet: standardavvikelsen för de dagliga avkastningarna senaste 12 månaderna, uppräknad till årstakt.</li>
<li>Rangordna från lägst till högst.</li>
<li>Köp de 50 lugnaste med lika vikt. Ombalansera varje kvartal.</li>
</ol>"""),
    S("Formeln", """
<div class="formula">σ = std(dagliga avkastningar, 252 dagar) × √252</div>"""),
    S("Vad säger forskningen?", """
<p>Effekten beskrevs redan av Haugen &amp; Heins (1975) och har bekräftats av bland andra Ang, Hodrick,
Xing &amp; Zhang (2006) och Baker, Bradley &amp; Wurgler (2011). Frazzini &amp; Pedersen ("Betting Against Beta",
2014) förklarar den med att många investerare inte får eller vill belåna sig och därför i stället köper
riskfyllda aktier för att få högre avkastning – vilket gör dem för dyra och de tråkiga aktierna för billiga.</p>"""),
    S("Risker och svagheter", """
<ul>
<li>Halkar efter kraftigt i snabba tjurmarknader, särskilt när tillväxt- och techbolag leder.</li>
<li>Övervikt i försvarssektorer som dagligvaror, försäkring och kraftbolag – känsliga för stigande räntor.</li>
<li>Skyddet är relativt: i en krasch faller även lugna aktier, bara mindre.</li>
</ul>"""),
    S("Så är den implementerad här", """
<p>Volatilitet på 252 handelsdagar (kräver minst 200), 30/50/100 aktier, ombalansering varje månad
eller kvartal.</p>"""),
]

_MF_CORE = [
    S("Idén i korthet", """
<p>Joel Greenblatts <b>Magic Formula</b> från boken <i>The Little Book That Beats the Market</i>
(2005) handlar om att köpa <b>bra bolag till lågt pris</b>. Två nyckeltal avgör:</p>
<ul>
<li><b>Earnings yield (EBIT/EV)</b> – hur mycket rörelseresultat du får för varje dollar du betalar för hela
bolaget, inklusive dess skulder. Högt = billigt.</li>
<li><b>Return on capital (ROC)</b> – hur mycket rörelseresultat bolaget skapar per dollar som är bunden i
verksamheten. Högt = bra affär.</li>
</ul>
<p>Bolagen rangordnas på båda måtten, rangerna läggs ihop och de med bäst sammanlagd rang köps.
Ett bolag som är näst billigast och tionde bäst slår alltså ett som är billigast men bara medelbra.</p>"""),
    S("Formeln", """
<div class="formula">
EV (enterprise value) = Börsvärde + Räntebärande skulder − Kassa<br>
Earnings yield = EBIT / EV<br><br>
Rörelsekapital = (Omsättningstillgångar − Kassa) − (Kortfristiga skulder − Kortfristiga lån)<br>
ROC = EBIT / (Rörelsekapital + Materiella anläggningstillgångar)<br><br>
Magic rank = rang(Earnings yield) + rang(ROC) &nbsp;&nbsp;→ lägst summa vinner
</div>
<p>EBIT (rörelseresultat) används i stället för nettovinst för att jämföra bolag med olika
skuldsättning och skattesatser rättvist. EV används i stället för börsvärde eftersom den som
köper ett helt bolag också tar över skulderna.</p>"""),
    S("Greenblatts regler", """
<ol>
<li>Välj ett minsta börsvärde (Greenblatt använde från 50 miljoner dollar och uppåt).</li>
<li>Uteslut <b>banker, försäkringsbolag och kraftbolag</b> (deras balansräkningar passar inte måtten) samt utländska bolag.</li>
<li>Rangordna på earnings yield och ROC, summera rangerna.</li>
<li>Köp 20–30 av de högst rankade bolagen, gärna 5–7 i taget med några månaders mellanrum under första året.</li>
<li>Behåll varje aktie i ett år, sälj och ersätt med nya högt rankade bolag.</li>
<li>Fortsätt i minst 3–5 år – strategin kan gå sämre än index flera år i rad.</li>
</ol>"""),
    S("Vad säger forskningen?", """
<p>Greenblatt redovisade cirka 30 % årlig avkastning 1988–2004 mot cirka 12 % för S&amp;P 500, för de
största 3 500 amerikanska bolagen. Senare oberoende studier har funnit att formeln fortsatt slå
marknaden men med mycket mindre marginal, och med långa perioder av underavkastning – särskilt
2017–2020 när "value" generellt gick dåligt. Gray &amp; Carlisle (<i>Quantitative Value</i>, 2012)
visade att <b>earnings yield ensam</b> historiskt gett lika bra eller bättre resultat än kombinationen,
vilket är grunden för <i>Acquirer's Multiple</i>-varianten här. Novy-Marx (2013) visade att
lönsamhetsmått (som ROC och bruttovinst/tillgångar) är en egen, stark faktor.</p>"""),
    S("Varför skulle det fungera?", """
<ul>
<li>Billiga aktier är ofta billiga för att de är <b>tråkiga eller har tillfälliga problem</b>. Marknaden
överreagerar på dåliga nyheter och prissätter in för mycket pessimism.</li>
<li>Kvalitetsfiltret (ROC) minskar risken att köpa bolag som är billiga för att de är dåliga ("value traps").</li>
<li>Strategin är <b>psykologiskt svår</b> att följa: listan är full av bolag med dåliga nyheter, och
den kan gå sämre än index i åratal. Greenblatts poäng är att det är just därför effekten kan bestå.</li>
</ul>"""),
    S("Risker och svagheter", """
<ul>
<li><b>Långa torrperioder</b>: flera år i rad under index är normalt.</li>
<li>Bokföringsdata kan vara missvisande – engångsposter, leasing och goodwill påverkar måtten.</li>
<li>Sektorkoncentration: ofta mycket detaljhandel, industri, energi eller utbildning.</li>
<li>Historiskt har effekten varit starkast bland små bolag som är dyrare och svårare att handla.</li>
<li>Här finns bara stora och medelstora bolag, och dagens indexmedlemmar (överlevnadsbias).</li>
</ul>"""),
]

_MF_IMPL = """
<p>Nyckeltalen kommer från bolagens 10-K och 10-Q hos SEC, och bara siffror som var
<b>publicerade</b> vid varje månadsskifte används. EBIT är senaste <b>helårsvärdet</b> (OperatingIncomeLoss,
med resultat före skatt som reserv). Balansposter tas från den senaste rapporten. Börsvärdet räknas
som kurs × utspädda aktier, justerat för splittar. Finans, fastigheter och kraftbolag är uteslutna.
Skulder exkluderar leasingskulder. Ett minsta börsvärde behövs inte eftersom alla bolag i universumet
redan är större än 1 miljard dollar.</p>"""

DOCS["mf_classic"] = [
    *_MF_CORE,
    S("Den här varianten", """
<p><b>Klassisk:</b> köp de 30 högst rankade bolagen vid ett tillfälle, behåll i 12 månader, byt sedan
ut hela portföljen mot den nya topplistan. Enkel att följa – men resultatet blir känsligt för vilken
månad du råkar starta (prova att ändra ombalanseringen).</p>"""),
    S("Så är den implementerad här", _MF_IMPL),
]

DOCS["mf_staggered"] = [
    *_MF_CORE,
    S("Den här varianten", """
<p><b>Rullande trancher</b> är så Greenblatt själv föreslår att man gör: portföljen delas i fyra
lika delar. Varje kvartal säljs den del som köptes för ett år sedan, och pengarna används för att köpa
de 8 högst rankade bolag du inte redan äger. Varje aktie hålls alltså i ungefär ett år, men
portföljen förnyas löpande. Det minskar risken att hela portföljen köps vid en olycklig tidpunkt och
gör resultatet mindre beroende av startmånaden.</p>"""),
    S("Så är den implementerad här", _MF_IMPL + """
<p>Förenkling: vid varje kvartalsskifte återställs portföljen så att varje tranch väger 25 % och
aktierna inom den lika mycket. Under det första året, innan alla fyra trancher finns, fördelas
pengarna på de trancher som köpts.</p>"""),
]

DOCS["mf_momentum"] = [
    *_MF_CORE,
    S("Den här varianten", """
<p><b>Magic Formula + momentum</b> angriper det största problemet med värdestrategier: att köpa
bolag som är billiga och <i>fortsätter</i> falla. Först tas en kandidatlista fram med de bäst
rankade Magic Formula-bolagen (t.ex. 3 × 30 = 90 bolag). Bland dem köps de 30 som haft högst
avkastning senaste 6 månaderna (exklusive senaste månaden).</p>
<p>Värde och momentum har historiskt varit <b>negativt korrelerade</b> – när den ena går dåligt går ofta
den andra bra – vilket gör kombinationen jämnare (Asness, Moskowitz &amp; Pedersen, "Value and Momentum
Everywhere", 2013).</p>"""),
    S("Så är den implementerad här", _MF_IMPL + """
<p>Momentum 6–1 på justerade kurser. Ombalansering varje kvartal som standard.</p>"""),
]

DOCS["mf_quality"] = [
    *_MF_CORE,
    S("Den här varianten", """
<p><b>Kvalitetsfilter:</b> samma rangordning som klassisk Magic Formula, men bolag med
<b>skuld/eget kapital över 1,0</b> eller <b>negativt nettoresultat</b> sorteras bort innan
de 30 bästa väljs. Tanken är att undvika de "billiga" bolag som är billiga för att de är
hårt belånade eller redan förlorar pengar – de som riskerar att gå från billiga till ännu billigare.</p>
<p>Filtret liknar idéerna i Piotroskis F-score (2000) och i Graham-inspirerade
kvalitetskrav: stark balansräkning först, pris sedan.</p>"""),
    S("Så är den implementerad här", _MF_IMPL + """
<p>Skuld = långfristiga + kortfristiga räntebärande skulder. Eget kapital måste vara positivt.</p>"""),
]

DOCS["acquirers_multiple"] = [
    *_MF_CORE,
    S("Den här varianten", """
<p><b>Acquirer's Multiple</b> (Tobias Carlisle) struntar i ROC och köper bara de bolag som har
<b>högst EBIT/EV</b> – det en företagsköpare skulle betala minst för, i förhållande till rörelseresultatet.
Carlisle och Gray fann att kvalitetsdelen i Magic Formula historiskt snarare dragit ned avkastningen,
eftersom bolag med mycket hög ROC ofta redan är dyra och deras höga lönsamhet tenderar att sjunka mot
genomsnittet. Den här varianten är renare "deep value" – och mer volatil.</p>"""),
    S("Så är den implementerad här", _MF_IMPL),
]

_ML_CORE = [
    S("Idén i korthet", """
<p>I stället för att en människa bestämmer formeln får en <b>maskininlärningsmodell</b> lära sig
från historiken vilka egenskaper som förutsett vilka aktier som går bäst nästa månad. Varje
månad beskrivs varje aktie av 15 variabler, modellen förutsäger dess <i>relativa</i> avkastning, och
de 30 med bäst prognos köps.</p>"""),
    S("Variablerna (features)", """
<table class="doc-table">
<tr><th>Grupp</th><th>Variabler</th></tr>
<tr><td>Momentum &amp; trend</td><td>Avkastning 1, 3, 6–1 och 12–1 månader, avstånd till 52-veckorshögsta</td></tr>
<tr><td>Risk</td><td>Volatilitet 12 månader</td></tr>
<tr><td>Värdering</td><td>EBIT/EV, vinst/börsvärde (E/P), eget kapital/börsvärde</td></tr>
<tr><td>Kvalitet</td><td>ROC, ROE, bruttovinst/tillgångar, skuld/eget kapital</td></tr>
<tr><td>Övrigt</td><td>Börsvärde (storlek), tillväxt i totala tillgångar</td></tr>
</table>
<p>Varje variabel görs om till en <b>percentilrang</b> varje månad (0 = lägst, 1 = högst bland alla
bolag den månaden). Det gör att modellen lär sig "billigare än andra" i stället för absoluta nivåer
som förändras över tid (räntor, värderingsnivåer). Målvariabeln är på samma sätt rangen av nästa
månads avkastning.</p>"""),
    S("Walk-forward-träning – varför den är ärlig", """
<p>Den vanligaste fällan med maskininlärning på aktier är att modellen av misstag får se
framtiden. Här tränas modellen därför <b>stegvis framåt i tiden</b>:</p>
<ol>
<li>I januari 2006 tränas modellen på all data 2001–2005.</li>
<li>Den modellen används för att välja aktier varje månad under 2006.</li>
<li>I januari 2007 tränas en ny modell på 2001–2006, och så vidare.</li>
</ol>
<p>Varje köpbeslut i backtesten är alltså gjort av en modell som aldrig sett utfallet. Totalt tränas
~20 modeller. Före 2009–2010 saknas SEC-nyckeltal, så de tidiga modellerna använder bara
kursvariabler.</p>"""),
    S("Hur man läser IC (informationskoefficient)", """
<p>IC är rangkorrelationen mellan modellens prognos och det faktiska utfallet nästa månad, räknad
varje månad. 0 = ingen förmåga, 1 = perfekt. <b>I aktier är en genomsnittlig IC på 0,02–0,05 bra</b>
– och även professionella modeller ligger ofta där. Låter det lite? Med 900 aktier och många månader
räcker en liten men stabil fördel långt – om den är verklig. Se andelen positiva månader och
t-värdet: under ~2 kan förmågan lika gärna vara slump.</p>"""),
    S("Vad säger forskningen?", """
<p>Gu, Kelly &amp; Xiu (<i>Empirical Asset Pricing via Machine Learning</i>, 2020) visade att trädmodeller
och neurala nät med ~900 variabler ungefär fördubblade Sharpekvoten jämfört med linjära modeller på
amerikanska aktier 1957–2016. Men en stor del av vinsten kom från små, illikvida aktier och
den försvinner delvis efter kostnader. Med bara stora bolag och 15 variabler som här ska man
förvänta sig mycket mindre.</p>"""),
    S("Risker och svagheter", """
<ul>
<li><b>Överanpassning:</b> modellen kan hitta mönster som bara är brus. Walk-forward skyddar mot fusk
men inte mot att mönstren slutar gälla.</li>
<li><b>Regimskiften:</b> det som fungerade 2005–2015 fungerar inte nödvändigtvis 2025.</li>
<li><b>Svartlåda:</b> det är svårt att förklara varför en viss aktie valts (se variabelbetydelsen nedan).</li>
<li>Hög omsättning vid månatlig ombalansering.</li>
</ul>"""),
]

DOCS["ml_gbm"] = [
    *_ML_CORE,
    S("Modellen: gradient boosting", """
<p><b>Gradient boosting</b> bygger hundratals små beslutsträd i följd. Varje nytt träd försöker
rätta till felen från de tidigare. Ett träd kan t.ex. lära sig regeln "om momentum är högt
<i>och</i> volatiliteten låg, förvänta högre avkastning" – det vill säga
<b>kombinationer och icke-linjära samband</b> som en linjär formel inte kan fånga.</p>
<p>Här används scikit-learns <code>HistGradientBoostingRegressor</code> med 200 träd, max 15 löv per
träd, minst 400 observationer per löv och L2-regularisering – avsiktligt försiktigt inställd eftersom
aktiedata är extremt brusig.</p>
<p><b>Variabelbetydelse</b> mäts med permutation: hur mycket sämre blir modellen om en variabel
blandas om slumpmässigt? Ju större försämring, desto viktigare variabel.</p>"""),
]

DOCS["ml_ridge"] = [
    *_ML_CORE,
    S("Modellen: Ridge-regression", """
<p><b>Ridge</b> är vanlig linjär regression med ett straff för stora koefficienter. Prognosen är
en viktad summa av de 15 variablerna:</p>
<div class="formula">prognos = b<sub>0</sub> + b<sub>1</sub>·momentum + b<sub>2</sub>·EBIT/EV + … + b<sub>15</sub>·tillväxt</div>
<p>Straffet (α = 50) drar koefficienterna mot noll så att modellen inte överanpassar sig till brus.
Fördelen är full genomskinlighet: koefficienterna nedan visar exakt vad modellen tror på. Positiv
koefficient = högre rang på variabeln ger högre förväntad avkastning. Den är i praktiken en
datadriven version av klassiska faktormodeller (Fama–French).</p>
<p>Saknade värden (t.ex. nyckeltal före 2010) sätts till medianrangen 0,5.</p>"""),
]
