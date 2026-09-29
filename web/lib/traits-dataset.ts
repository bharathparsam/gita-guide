import type { TraitExplanation } from "./types";

export const gitaTraits = [
  {
    id: "anxiety",
    label: "Anxiety",
    type: "emotion",
    aliases: ["anxious", "worried", "uneasy", "panic", "nervous"],
    krishnaSaid: "Do not let anxiety and external disturbance control your inner state.",
    howToOvercome: "Steady the mind, reduce attachment to outcomes, and return attention to Krishna and your duty.",
    verse: "12.15",
    sloka: `yasmān nodvijate loko
lokān nodvijate ca yaḥ
harṣāmarṣa-bhayodvegair
mukto yaḥ sa ca me priyaḥ`
  },

  {
    id: "fear",
    label: "Fear",
    type: "emotion",
    aliases: ["afraid", "scared", "fearful", "terrified", "insecure"],
    krishnaSaid: "A steady person becomes free from attachment, fear, and anger.",
    howToOvercome: "Strengthen steadiness of mind and do not let imagined outcomes dictate your action.",
    verse: "2.56",
    sloka: `duḥkheṣv anudvigna-manāḥ
sukheṣu vigata-spṛhaḥ
vīta-rāga-bhaya-krodhaḥ
sthita-dhīr munir ucyate`
  },

  {
    id: "worry",
    label: "Worry",
    type: "emotion",
    aliases: ["worried", "concerned", "uneasy", "stressed", "what if"],
    krishnaSaid: "Do not be constantly disturbed by anxiety about what may happen.",
    howToOvercome: "Return from imagined futures to the duty and response available now.",
    verse: "12.15",
    sloka: `yasmān nodvijate loko
lokān nodvijate ca yaḥ
harṣāmarṣa-bhayodvegair
mukto yaḥ sa ca me priyaḥ`
  },

  {
    id: "grief",
    label: "Grief",
    type: "emotion",
    aliases: ["grieving", "sorrow", "bereavement", "heartbroken", "mourning"],
    krishnaSaid: "Happiness and distress appear and disappear like changing seasons.",
    howToOvercome: "Allow grief to be felt without treating the present pain as permanent; endure and continue wisely.",
    verse: "2.14",
    sloka: `mātrā-sparśās tu kaunteya
śītoṣṇa-sukha-duḥkha-dāḥ
āgamāpāyino 'nityās
tāṁs titikṣasva bhārata`
  },

  {
    id: "sadness",
    label: "Sadness",
    type: "emotion",
    aliases: ["sad", "down", "unhappy", "low", "sorrowful"],
    krishnaSaid: "Pleasure and pain are temporary experiences that come and go.",
    howToOvercome: "Do not build your identity around a passing emotional state; tolerate it and keep moving toward right action.",
    verse: "2.14",
    sloka: `mātrā-sparśās tu kaunteya
śītoṣṇa-sukha-duḥkha-dāḥ
āgamāpāyino 'nityās
tāṁs titikṣasva bhārata`
  },

  {
    id: "distress",
    label: "Distress",
    type: "emotion",
    aliases: ["distressed", "overwhelmed", "troubled", "agitated", "upset"],
    krishnaSaid: "The steady-minded person is not internally overthrown by distress.",
    howToOvercome: "Acknowledge the difficulty, then protect your judgment from being ruled by it.",
    verse: "2.56",
    sloka: `duḥkheṣv anudvigna-manāḥ
sukheṣu vigata-spṛhaḥ
vīta-rāga-bhaya-krodhaḥ
sthita-dhīr munir ucyate`
  },

  {
    id: "moroseness",
    label: "Moroseness",
    type: "emotion",
    aliases: ["gloomy", "hopeless", "withdrawn", "dejected", "despondent"],
    krishnaSaid: "Remaining trapped in fear, lamentation, moroseness, and illusion is a dark form of determination.",
    howToOvercome: "Break the loop through disciplined action, clearer thinking, and regulated habits.",
    verse: "18.35",
    sloka: `yayā svapnaṁ bhayaṁ śokaṁ
viṣādaṁ madam eva ca
na vimuñcati durmedhā
dhṛtiḥ sā pārtha tāmasī`
  },

  {
    id: "overthinking",
    label: "Overthinking",
    type: "mind",
    aliases: ["ruminating", "thinking too much", "mental loop", "cannot stop thinking", "spiraling"],
    krishnaSaid: "An uncontrolled mind behaves like an enemy; a conquered mind becomes a friend.",
    howToOvercome: "Stop obeying every thought. Train attention and repeatedly return the mind to what matters.",
    verse: "6.6",
    sloka: `bandhur ātmātmanas tasya
yenātmaivātmanā jitaḥ
anātmanas tu śatrutve
vartetātmaiva śatru-vat`
  },

  {
    id: "restless_mind",
    label: "Restless Mind",
    type: "mind",
    aliases: ["restless", "racing thoughts", "unsettled mind", "cannot focus", "flickering mind"],
    krishnaSaid: "The mind is difficult and restless, but it can be controlled by practice and detachment.",
    howToOvercome: "Use repeated practice and reduce attachment to whatever keeps pulling the mind away.",
    verse: "6.35",
    sloka: `śrī-bhagavān uvāca
asaṁśayaṁ mahā-bāho
mano durnigrahaṁ calam
abhyāsena tu kaunteya
vairāgyeṇa ca gṛhyate`
  },

  {
    id: "distraction",
    label: "Distraction",
    type: "mind",
    aliases: ["distracted", "cannot focus", "mind wandering", "losing focus", "attention problem"],
    krishnaSaid: "Whenever the mind wanders, bring it back under control.",
    howToOvercome: "Notice the distraction without frustration and deliberately return attention again and again.",
    verse: "6.26",
    sloka: `yato yato niścalati
manaś cañcalam asthiram
tatas tato niyamyaitad
ātmany eva vaśaṁ nayet`
  },

  {
    id: "confusion",
    label: "Confusion",
    type: "mind",
    aliases: ["confused", "unclear", "lost", "bewildered", "cannot think clearly"],
    krishnaSaid: "Anger and delusion disturb memory and destroy sound judgment.",
    howToOvercome: "Pause before reacting; cool the emotion first, then decide with a clearer mind.",
    verse: "2.63",
    sloka: `krodhād bhavati sammohaḥ
sammohāt smṛti-vibhramaḥ
smṛti-bhraṁśād buddhi-nāśo
buddhi-nāśāt praṇaśyati`
  },

  {
    id: "doubt",
    label: "Doubt",
    type: "mind",
    aliases: ["doubtful", "uncertain belief", "skeptical", "second guessing", "lack of faith"],
    krishnaSaid: "Persistent doubt prevents peace and progress.",
    howToOvercome: "Seek sound knowledge, examine carefully, and commit once understanding is clear.",
    verse: "4.40",
    sloka: `ajñaś cāśraddadhānaś ca
saṁśayātmā vinaśyati
nāyaṁ loko 'sti na paro
na sukhaṁ saṁśayātmanaḥ`
  },

  {
    id: "indecision",
    label: "Indecision",
    type: "mind",
    aliases: ["cannot decide", "stuck choosing", "conflicted", "decision paralysis", "unsure what to do"],
    krishnaSaid: "Understand fully, reflect carefully, and then choose.",
    howToOvercome: "Gather what matters, deliberate, then act instead of remaining indefinitely stuck.",
    verse: "18.63",
    sloka: `iti te jñānam ākhyātaṁ
guhyād guhyataraṁ mayā
vimṛśyaitad aśeṣeṇa
yathecchasi tathā kuru`
  },

  {
    id: "self_doubt",
    label: "Self-Doubt",
    type: "mind",
    aliases: ["not good enough", "doubting myself", "low confidence", "I cannot do it", "self criticism"],
    krishnaSaid: "Elevate yourself through the mind rather than letting the mind degrade you.",
    howToOvercome: "Train your inner dialogue to support disciplined action instead of repeatedly weakening you.",
    verse: "6.5",
    sloka: `uddhared ātmanātmānaṁ
nātmānam avasādayet
ātmaiva hy ātmano bandhur
ātmaiva ripur ātmanaḥ`
  },

  {
    id: "anger",
    label: "Anger",
    type: "emotion",
    aliases: ["angry", "furious", "rage", "irritated", "mad"],
    krishnaSaid: "Attachment creates desire, and frustrated desire can become anger.",
    howToOvercome: "Trace the anger back to the expectation or attachment underneath it and loosen that grip before reacting.",
    verse: "2.62",
    sloka: `dhyāyato viṣayān puṁsaḥ
saṅgas teṣūpajāyate
saṅgāt sañjāyate kāmaḥ
kāmāt krodho 'bhijāyate`
  },

  {
    id: "frustration",
    label: "Frustration",
    type: "emotion",
    aliases: ["frustrated", "annoyed", "blocked", "fed up", "irritated"],
    krishnaSaid: "When desire is obstructed, anger can arise.",
    howToOvercome: "Separate what you want from what you can control, and act on the controllable part.",
    verse: "2.62",
    sloka: `dhyāyato viṣayān puṁsaḥ
saṅgas teṣūpajāyate
saṅgāt sañjāyate kāmaḥ
kāmāt krodho 'bhijāyate`
  },

  {
    id: "lust",
    label: "Lust",
    type: "desire",
    aliases: ["lustful", "sexual craving", "uncontrolled desire", "sensual craving", "tempted"],
    krishnaSaid: "Uncontrolled lust covers knowledge and burns like a fire that is never satisfied.",
    howToOvercome: "Do not feed craving expecting it to end; regulate the senses and redirect the mind toward a higher purpose.",
    verse: "3.39",
    sloka: `āvṛtaṁ jñānam etena
jñānino nitya-vairiṇā
kāma-rūpeṇa kaunteya
duṣpūreṇānalena ca`
  },

  {
    id: "greed",
    label: "Greed",
    type: "desire",
    aliases: ["greedy", "want more", "never enough", "avarice", "material hunger"],
    krishnaSaid: "Lust, anger, and greed are destructive forces that should be abandoned.",
    howToOvercome: "Recognize the point where legitimate need becomes endless wanting, then deliberately limit and redirect desire.",
    verse: "16.21",
    sloka: `tri-vidhaṁ narakasyedaṁ
dvāraṁ nāśanam ātmanaḥ
kāmaḥ krodhas tathā lobhas
tasmād etat trayaṁ tyajet`
  },

  {
    id: "attachment",
    label: "Attachment",
    type: "desire",
    aliases: ["attached", "clingy", "cannot let go", "possessive", "dependent"],
    krishnaSaid: "Repeated contemplation creates attachment, and attachment generates desire.",
    howToOvercome: "Watch what the mind repeatedly dwells on; redirect attention before attachment grows into compulsion.",
    verse: "2.62",
    sloka: `dhyāyato viṣayān puṁsaḥ
saṅgas teṣūpajāyate
saṅgāt sañjāyate kāmaḥ
kāmāt krodho 'bhijāyate`
  },

  {
    id: "obsession",
    label: "Obsession",
    type: "desire",
    aliases: ["obsessed", "fixated", "cannot stop thinking about it", "preoccupied", "consumed"],
    krishnaSaid: "What you continually contemplate can grow into attachment and desire.",
    howToOvercome: "Reduce repeated mental feeding of the object and re-engage the mind in purposeful activity.",
    verse: "2.62",
    sloka: `dhyāyato viṣayān puṁsaḥ
saṅgas teṣūpajāyate
saṅgāt sañjāyate kāmaḥ
kāmāt krodho 'bhijāyate`
  },

  {
    id: "temptation",
    label: "Temptation",
    type: "desire",
    aliases: ["tempted", "urge", "craving", "impulse", "cannot resist"],
    krishnaSaid: "Control the senses early before desire destroys knowledge and self-mastery.",
    howToOvercome: "Change the environment and input before relying only on willpower at the final moment.",
    verse: "3.41",
    sloka: `tasmāt tvam indriyāṇy ādau
niyamya bharatarṣabha
pāpmānaṁ prajahi hy enaṁ
jñāna-vijñāna-nāśanam`
  },

  {
    id: "addictive_desire",
    label: "Addictive Desire",
    type: "desire",
    aliases: ["addicted", "compulsive craving", "cannot stop", "need more", "urge keeps returning"],
    krishnaSaid: "Desire can behave like a fire that remains unsatisfied no matter how much fuel it receives.",
    howToOvercome: "Stop using repeated indulgence as the cure; reduce triggers, regulate the senses, and cultivate a higher engagement.",
    verse: "3.39",
    sloka: `āvṛtaṁ jñānam etena
jñānino nitya-vairiṇā
kāma-rūpeṇa kaunteya
duṣpūreṇānalena ca`
  },

  {
    id: "fear_of_failure",
    label: "Fear of Failure",
    type: "work",
    aliases: ["afraid to fail", "what if I fail", "failure anxiety", "scared to try", "performance fear"],
    krishnaSaid: "Your responsibility is to perform the action, not to own the result.",
    howToOvercome: "Define the next right action and execute it well instead of mentally rehearsing the outcome.",
    verse: "2.47",
    sloka: `karmaṇy evādhikāras te
mā phaleṣu kadācana
mā karma-phala-hetur bhūr
mā te saṅgo 'stv akarmaṇi`
  },

  {
    id: "failure",
    label: "Failure",
    type: "work",
    aliases: ["failed", "lost", "did not succeed", "setback", "unsuccessful"],
    krishnaSaid: "Remain balanced in success and failure while continuing your duty.",
    howToOvercome: "Review what happened, learn, adjust, and continue without turning one result into your identity.",
    verse: "2.48",
    sloka: `yoga-sthaḥ kuru karmāṇi
saṅgaṁ tyaktvā dhanañjaya
siddhy-asiddhyoḥ samo bhūtvā
samatvaṁ yoga ucyate`
  },

  {
    id: "success",
    label: "Success",
    type: "work",
    aliases: ["succeeded", "won", "achievement", "victory", "doing well"],
    krishnaSaid: "Success should not destroy inner balance any more than failure should.",
    howToOvercome: "Accept success with gratitude, but stay focused on duty instead of becoming attached to the win.",
    verse: "2.48",
    sloka: `yoga-sthaḥ kuru karmāṇi
saṅgaṁ tyaktvā dhanañjaya
siddhy-asiddhyoḥ samo bhūtvā
samatvaṁ yoga ucyate`
  },

  {
    id: "result_obsession",
    label: "Result Obsession",
    type: "work",
    aliases: ["obsessed with outcome", "results anxiety", "need to win", "scoreboard thinking", "outcome fixation"],
    krishnaSaid: "You control your action, but you do not control every fruit of that action.",
    howToOvercome: "Move attention from 'What will I get?' to 'What is the right action I can perform now?'",
    verse: "2.47",
    sloka: `karmaṇy evādhikāras te
mā phaleṣu kadācana
mā karma-phala-hetur bhūr
mā te saṅgo 'stv akarmaṇi`
  },

  {
    id: "performance_pressure",
    label: "Performance Pressure",
    type: "work",
    aliases: ["pressure to perform", "work stress", "exam pressure", "target pressure", "must succeed"],
    krishnaSaid: "Act steadily without attaching your inner stability to success or failure.",
    howToOvercome: "Prepare and execute fully, then let the result be separate from your self-worth.",
    verse: "2.48",
    sloka: `yoga-sthaḥ kuru karmāṇi
saṅgaṁ tyaktvā dhanañjaya
siddhy-asiddhyoḥ samo bhūtvā
samatvaṁ yoga ucyate`
  },

  {
    id: "procrastination",
    label: "Procrastination",
    type: "work",
    aliases: ["procrastinating", "delaying", "putting off", "avoiding work", "not starting"],
    krishnaSaid: "Do not become attached to inaction.",
    howToOvercome: "Shrink the duty to the next concrete step and begin before waiting for motivation or certainty.",
    verse: "2.47",
    sloka: `karmaṇy evādhikāras te
mā phaleṣu kadācana
mā karma-phala-hetur bhūr
mā te saṅgo 'stv akarmaṇi`
  },

  {
    id: "career_comparison",
    label: "Career Comparison",
    type: "work",
    aliases: ["comparing careers", "behind others", "career jealousy", "someone is ahead", "wrong career path"],
    krishnaSaid: "It is better to perform your own duty imperfectly than imitate another person's path perfectly.",
    howToOvercome: "Build according to your nature, responsibilities, and strengths instead of copying someone else's timeline.",
    verse: "18.47",
    sloka: `śreyān sva-dharmo viguṇaḥ
para-dharmāt sv-anuṣṭhitāt
svabhāva-niyataṁ karma
kurvan nāpnoti kilbiṣam`
  },

  {
    id: "purpose",
    label: "Purpose",
    type: "work",
    aliases: ["life purpose", "meaning", "what should I do", "calling", "direction"],
    krishnaSaid: "A person can move toward perfection through the sincere performance of their own work offered to the Supreme.",
    howToOvercome: "Look for the intersection of your nature, responsibility, service, and spiritual orientation.",
    verse: "18.46",
    sloka: `yataḥ pravṛttir bhūtānāṁ
yena sarvam idaṁ tatam
sva-karmaṇā tam abhyarcya
siddhiṁ vindati mānavaḥ`
  },

  {
    id: "motivation",
    label: "Motivation",
    type: "work",
    aliases: ["unmotivated", "need motivation", "lost drive", "no enthusiasm", "cannot push myself"],
    krishnaSaid: "The good worker acts with determination and enthusiasm without being shaken by success or failure.",
    howToOvercome: "Build action around commitment and purpose rather than waiting for a temporary feeling of motivation.",
    verse: "18.26",
    sloka: `mukta-saṅgo 'nahaṁ-vādī
dhṛty-utsāha-samanvitaḥ
siddhy-asiddhyor nirvikāraḥ
kartā sāttvika ucyate`
  },

  {
    id: "discipline",
    label: "Discipline",
    type: "habit",
    aliases: ["disciplined", "consistency", "routine", "self discipline", "stay consistent"],
    krishnaSaid: "Good determination steadily governs the mind, life energy, and senses.",
    howToOvercome: "Use repeatable routines and commitments that continue even when mood changes.",
    verse: "18.33",
    sloka: `dhṛtyā yayā dhārayate
manaḥ-prāṇendriya-kriyāḥ
yogenāvyabhicāriṇyā
dhṛtiḥ sā pārtha sāttvikī`
  },

  {
    id: "laziness",
    label: "Laziness",
    type: "habit",
    aliases: ["lazy", "lethargic", "inactive", "sluggish", "do nothing"],
    krishnaSaid: "Remaining stuck in excessive sleep, fear, lamentation, and inertia is a form of dark determination.",
    howToOvercome: "Use regulated sleep, movement, and small duties to create momentum instead of negotiating endlessly with inertia.",
    verse: "18.35",
    sloka: `yayā svapnaṁ bhayaṁ śokaṁ
viṣādaṁ madam eva ca
na vimuñcati durmedhā
dhṛtiḥ sā pārtha tāmasī`
  },

  {
    id: "oversleeping",
    label: "Oversleeping",
    type: "habit",
    aliases: ["sleeping too much", "cannot wake up", "too much sleep", "lazy mornings", "over sleeping"],
    krishnaSaid: "Neither excessive sleep nor insufficient sleep supports balanced yoga.",
    howToOvercome: "Set a regular sleep-wake rhythm and avoid both indulgence and deprivation.",
    verse: "6.16",
    sloka: `nāty-aśnatas tu yogo 'sti
na caikāntam anaśnataḥ
na cāti-svapna-śīlasya
jāgrato naiva cārjuna`
  },

  {
    id: "poor_routine",
    label: "Poor Routine",
    type: "habit",
    aliases: ["no routine", "irregular schedule", "bad habits", "chaotic lifestyle", "inconsistent day"],
    krishnaSaid: "Balanced eating, recreation, work, sleep, and wakefulness reduce suffering.",
    howToOvercome: "Regulate the basic rhythms of the day before trying to solve everything through motivation.",
    verse: "6.17",
    sloka: `yuktāhāra-vihārasya
yukta-ceṣṭasya karmasu
yukta-svapnāvabodhasya
yogo bhavati duḥkha-hā`
  },

  {
    id: "lack_of_self_control",
    label: "Lack of Self-Control",
    type: "habit",
    aliases: ["no self control", "cannot control myself", "weak willpower", "giving in", "undisciplined"],
    krishnaSaid: "An uncontrolled mind becomes an enemy; a controlled mind becomes a friend.",
    howToOvercome: "Build control gradually through repeated choices, environmental limits, and intentional attention.",
    verse: "6.6",
    sloka: `bandhur ātmātmanas tasya
yenātmaivātmanā jitaḥ
anātmanas tu śatrutve
vartetātmaiva śatru-vat`
  },

  {
    id: "impulsiveness",
    label: "Impulsiveness",
    type: "habit",
    aliases: ["impulsive", "act without thinking", "quick reaction", "urge driven", "rash"],
    krishnaSaid: "The senses should be regulated before destructive desire gains strength.",
    howToOvercome: "Create a pause between urge and action and remove easy access to the trigger when possible.",
    verse: "3.41",
    sloka: `tasmāt tvam indriyāṇy ādau
niyamya bharatarṣabha
pāpmānaṁ prajahi hy enaṁ
jñāna-vijñāna-nāśanam`
  },

  {
    id: "extreme_behaviour",
    label: "Extreme Behaviour",
    type: "habit",
    aliases: ["all or nothing", "extreme dieting", "overworking", "too much or too little", "unsustainable"],
    krishnaSaid: "Neither excess nor severe deprivation supports a balanced path.",
    howToOvercome: "Choose sustainable moderation instead of swinging between extremes.",
    verse: "6.16",
    sloka: `nāty-aśnatas tu yogo 'sti
na caikāntam anaśnataḥ
na cāti-svapna-śīlasya
jāgrato naiva cārjuna`
  },

  {
    id: "jealousy",
    label: "Jealousy",
    type: "relationship",
    aliases: ["jealous", "comparing", "possessive jealousy", "envy", "someone has more"],
    krishnaSaid: "Be free from envy and cultivate friendliness and compassion toward all beings.",
    howToOvercome: "Turn comparison into goodwill, and redirect attention toward your own duty and growth.",
    verse: "12.13",
    sloka: `adveṣṭā sarva-bhūtānāṁ
maitraḥ karuṇa eva ca
nirmamo nirahaṅkāraḥ
sama-duḥkha-sukhaḥ kṣamī`
  },

  {
    id: "envy",
    label: "Envy",
    type: "relationship",
    aliases: ["envious", "resenting success", "jealous of others", "wish I had that", "comparison"],
    krishnaSaid: "The devotee is not envious and is friendly and compassionate toward others.",
    howToOvercome: "Bless another person's good without using it as evidence that your own life is lesser.",
    verse: "12.13",
    sloka: `adveṣṭā sarva-bhūtānāṁ
maitraḥ karuṇa eva ca
nirmamo nirahaṅkāraḥ
sama-duḥkha-sukhaḥ kṣamī`
  },

  {
    id: "hatred",
    label: "Hatred",
    type: "relationship",
    aliases: ["hate", "hateful", "despise", "enemy", "cannot stand them"],
    krishnaSaid: "Cultivate freedom from hatred and friendliness toward living beings.",
    howToOvercome: "Reject harmful behavior where necessary, but do not let hatred become the ruler of your own mind.",
    verse: "12.13",
    sloka: `adveṣṭā sarva-bhūtānāṁ
maitraḥ karuṇa eva ca
nirmamo nirahaṅkāraḥ
sama-duḥkha-sukhaḥ kṣamī`
  },

  {
    id: "resentment",
    label: "Resentment",
    type: "relationship",
    aliases: ["resentful", "holding a grudge", "cannot forgive", "bitter", "replaying hurt"],
    krishnaSaid: "Friendliness, compassion, freedom from ego, and forgiveness are qualities Krishna praises.",
    howToOvercome: "Stop feeding the injury through repeated mental replay; choose boundaries without living inside the grievance.",
    verse: "12.13",
    sloka: `adveṣṭā sarva-bhūtānāṁ
maitraḥ karuṇa eva ca
nirmamo nirahaṅkāraḥ
sama-duḥkha-sukhaḥ kṣamī`
  },

  {
    id: "forgiveness",
    label: "Forgiveness",
    type: "virtue",
    aliases: ["forgive", "forgiving", "let go", "release resentment", "pardon"],
    krishnaSaid: "Forgiveness and fortitude are divine qualities.",
    howToOvercome: "Release the need to keep punishing yourself with another person's past action while still keeping wise boundaries.",
    verse: "16.3",
    sloka: `tejaḥ kṣamā dhṛtiḥ śaucam
adroho nātimānitā
bhavanti sampadaṁ daivīm
abhijātasya bhārata`
  },

  {
    id: "conflict",
    label: "Conflict",
    type: "relationship",
    aliases: ["argument", "fighting", "relationship conflict", "enemy", "disagreement"],
    krishnaSaid: "Remain balanced toward friend and enemy and through honor and dishonor.",
    howToOvercome: "Respond from principle rather than allowing the other person's behavior to completely determine yours.",
    verse: "12.18",
    sloka: `samaḥ śatrau ca mitre ca
tathā mānāpamānayoḥ
śītoṣṇa-sukha-duḥkheṣu
samaḥ saṅga-vivarjitaḥ`
  },

  {
    id: "insult",
    label: "Insult",
    type: "relationship",
    aliases: ["insulted", "disrespected", "humiliated", "dishonored", "offended"],
    krishnaSaid: "Honor and dishonor are conditions through which the steady person remains balanced.",
    howToOvercome: "Do not hand another person's words total control over your self-worth or conduct.",
    verse: "12.18",
    sloka: `samaḥ śatrau ca mitre ca
tathā mānāpamānayoḥ
śītoṣṇa-sukha-duḥkheṣu
samaḥ saṅga-vivarjitaḥ`
  },

  {
    id: "criticism",
    label: "Criticism",
    type: "relationship",
    aliases: ["criticized", "blamed", "negative feedback", "people judging me", "defamed"],
    krishnaSaid: "Remain steady through praise and blame.",
    howToOvercome: "Extract useful truth from criticism, discard what is false, and avoid becoming addicted to praise.",
    verse: "12.19",
    sloka: `tulya-nindā-stutir maunī
santuṣṭo yena kenacit
aniketaḥ sthira-matir
bhaktimān me priyo naraḥ`
  },

  {
    id: "need_for_approval",
    label: "Need for Approval",
    type: "relationship",
    aliases: ["need validation", "people pleasing", "want approval", "want respect", "seeking praise"],
    krishnaSaid: "Freedom from excessive desire for honor is a divine quality.",
    howToOvercome: "Let values and right action matter more than applause, status, or recognition.",
    verse: "16.3",
    sloka: `tejaḥ kṣamā dhṛtiḥ śaucam
adroho nātimānitā
bhavanti sampadaṁ daivīm
abhijātasya bhārata`
  },

  {
    id: "harsh_speech",
    label: "Harsh Speech",
    type: "relationship",
    aliases: ["rude", "hurtful words", "shouting", "speaking harshly", "verbal anger"],
    krishnaSaid: "Speech should be truthful, beneficial, and non-agitating.",
    howToOvercome: "Before speaking, ask whether the words are true, useful, and capable of being expressed without needless harm.",
    verse: "17.15",
    sloka: `anudvega-karaṁ vākyaṁ
satyaṁ priya-hitaṁ ca yat
svādhyāyābhyasanaṁ caiva
vāṅ-mayaṁ tapa ucyate`
  },

  {
    id: "compassion",
    label: "Compassion",
    type: "virtue",
    aliases: ["kindness", "empathy", "care", "merciful", "helping others"],
    krishnaSaid: "Be friendly and compassionate toward all living beings.",
    howToOvercome: "Move from merely noticing suffering to responding with useful, non-egoistic help.",
    verse: "12.13",
    sloka: `adveṣṭā sarva-bhūtānāṁ
maitraḥ karuṇa eva ca
nirmamo nirahaṅkāraḥ
sama-duḥkha-sukhaḥ kṣamī`
  },

  {
    id: "pride",
    label: "Pride",
    type: "ego",
    aliases: ["proud", "too proud", "egoistic pride", "superiority", "boastful"],
    krishnaSaid: "Pride and arrogance are qualities that bind rather than liberate.",
    howToOvercome: "Let achievement increase responsibility and gratitude instead of superiority.",
    verse: "16.4",
    sloka: `dambho darpo 'bhimānaś ca
krodhaḥ pāruṣyam eva ca
ajñānaṁ cābhijātasya
pārtha sampadam āsurīm`
  },

  {
    id: "arrogance",
    label: "Arrogance",
    type: "ego",
    aliases: ["arrogant", "superior", "conceited", "look down on others", "egoistic"],
    krishnaSaid: "Arrogance, pride, conceit, anger, and harshness are destructive qualities.",
    howToOvercome: "Remain teachable, accept correction, and separate competence from superiority.",
    verse: "16.4",
    sloka: `dambho darpo 'bhimānaś ca
krodhaḥ pāruṣyam eva ca
ajñānaṁ cābhijātasya
pārtha sampadam āsurīm`
  },

  {
    id: "ego",
    label: "Ego",
    type: "ego",
    aliases: ["ego", "false ego", "self importance", "I am better", "identity attachment"],
    krishnaSaid: "Freedom from false ego and possessiveness is part of the character Krishna praises.",
    howToOvercome: "Do not reduce your identity to title, possession, praise, or temporary success.",
    verse: "12.13",
    sloka: `adveṣṭā sarva-bhūtānāṁ
maitraḥ karuṇa eva ca
nirmamo nirahaṅkāraḥ
sama-duḥkha-sukhaḥ kṣamī`
  },

  {
    id: "need_for_recognition",
    label: "Need for Recognition",
    type: "ego",
    aliases: ["want recognition", "want credit", "need praise", "want status", "want attention"],
    krishnaSaid: "Discipline performed mainly for honor and recognition is unstable and driven by passion.",
    howToOvercome: "Do worthwhile work even when nobody notices, and check whether recognition has become the real motive.",
    verse: "17.18",
    sloka: `satkāra-māna-pūjārthaṁ
tapo dambhena caiva yat
kriyate tad iha proktaṁ
rājasaṁ calam adhruvam`
  },

  {
    id: "show_off",
    label: "Show-Off Behaviour",
    type: "ego",
    aliases: ["showing off", "boasting", "performative", "trying to impress", "attention seeking"],
    krishnaSaid: "Actions performed to gain respect and worship are unstable and externally driven.",
    howToOvercome: "Choose substance over display and ask whether you would still do the act without an audience.",
    verse: "17.18",
    sloka: `satkāra-māna-pūjārthaṁ
tapo dambhena caiva yat
kriyate tad iha proktaṁ
rājasaṁ calam adhruvam`
  },

  {
    id: "humility",
    label: "Humility",
    type: "virtue",
    aliases: ["humble", "modest", "teachability", "no pride", "grounded"],
    krishnaSaid: "Humility, absence of pretence, nonviolence, patience, simplicity, and self-control are forms of knowledge.",
    howToOvercome: "Stay open to correction, learn from others, and avoid unnecessary self-importance.",
    verse: "13.8",
    sloka: `amānitvam adambhitvam
ahiṁsā kṣāntir ārjavam
ācāryopāsanaṁ śaucaṁ
sthairyam ātma-vinigrahaḥ`
  },

  {
    id: "calmness",
    label: "Calmness",
    type: "virtue",
    aliases: ["calm", "peaceful", "tranquil", "composed", "steady"],
    krishnaSaid: "A conquered mind brings tranquility and steadiness through changing circumstances.",
    howToOvercome: "Train the mind rather than demanding that the environment become perfect first.",
    verse: "6.7",
    sloka: `jitātmanaḥ praśāntasya
paramātmā samāhitaḥ
śītoṣṇa-sukha-duḥkheṣu
tathā mānāpamānayoḥ`
  },

  {
    id: "equanimity",
    label: "Equanimity",
    type: "virtue",
    aliases: ["balanced", "even minded", "stable", "unshaken", "same in success and failure"],
    krishnaSaid: "Evenness of mind in success and failure is yoga.",
    howToOvercome: "Keep effort high while reducing emotional dependence on the result.",
    verse: "2.48",
    sloka: `yoga-sthaḥ kuru karmāṇi
saṅgaṁ tyaktvā dhanañjaya
siddhy-asiddhyoḥ samo bhūtvā
samatvaṁ yoga ucyate`
  },

  {
    id: "contentment",
    label: "Contentment",
    type: "virtue",
    aliases: ["content", "satisfied", "enough", "grateful", "at peace"],
    krishnaSaid: "The devoted person is content, self-controlled, and firmly determined.",
    howToOvercome: "Practice gratitude, reduce unnecessary wants, and keep the mind anchored in something higher than acquisition.",
    verse: "12.14",
    sloka: `santuṣṭaḥ satataṁ yogī
yatātmā dṛḍha-niścayaḥ
mayy arpita-mano-buddhir
yo mad-bhaktaḥ sa me priyaḥ`
  },

  {
    id: "patience",
    label: "Patience",
    type: "virtue",
    aliases: ["patient", "waiting", "impatient", "endure", "hold steady"],
    krishnaSaid: "Pleasure and pain are temporary and should be tolerated with steadiness.",
    howToOvercome: "Do not make permanent decisions from temporary discomfort; endure long enough to respond wisely.",
    verse: "2.14",
    sloka: `mātrā-sparśās tu kaunteya
śītoṣṇa-sukha-duḥkha-dāḥ
āgamāpāyino 'nityās
tāṁs titikṣasva bhārata`
  },

  {
    id: "tolerance",
    label: "Tolerance",
    type: "virtue",
    aliases: ["tolerate", "endurance", "bear discomfort", "resilience", "forbearance"],
    krishnaSaid: "Changing experiences of comfort and discomfort are temporary.",
    howToOvercome: "Observe the discomfort, avoid unnecessary reaction, and continue the right action where possible.",
    verse: "2.14",
    sloka: `mātrā-sparśās tu kaunteya
śītoṣṇa-sukha-duḥkha-dāḥ
āgamāpāyino 'nityās
tāṁs titikṣasva bhārata`
  },

  {
    id: "courage",
    label: "Courage",
    type: "virtue",
    aliases: ["brave", "courageous", "face fear", "bold", "strength"],
    krishnaSaid: "Fearlessness is the first quality Krishna lists among the divine qualities.",
    howToOvercome: "Act from clarity and principle instead of allowing fear alone to choose your behavior.",
    verse: "16.1",
    sloka: `abhayaṁ sattva-saṁśuddhir
jñāna-yoga-vyavasthitiḥ
dānaṁ damaś ca yajñaś ca
svādhyāyas tapa ārjavam`
  },

  {
    id: "fearlessness",
    label: "Fearlessness",
    type: "virtue",
    aliases: ["fearless", "without fear", "brave", "unafraid", "confidence"],
    krishnaSaid: "Fearlessness belongs to divine character.",
    howToOvercome: "Strengthen knowledge, self-control, and spiritual orientation so fear does not dominate action.",
    verse: "16.1",
    sloka: `abhayaṁ sattva-saṁśuddhir
jñāna-yoga-vyavasthitiḥ
dānaṁ damaś ca yajñaś ca
svādhyāyas tapa ārjavam`
  },

  {
    id: "determination",
    label: "Determination",
    type: "virtue",
    aliases: ["determined", "resolve", "commitment", "perseverance", "will"],
    krishnaSaid: "Good determination steadily controls the mind, life, and senses through unbroken practice.",
    howToOvercome: "Turn intention into repeatable commitments that survive changing moods.",
    verse: "18.33",
    sloka: `dhṛtyā yayā dhārayate
manaḥ-prāṇendriya-kriyāḥ
yogenāvyabhicāriṇyā
dhṛtiḥ sā pārtha sāttvikī`
  },

  {
    id: "fortitude",
    label: "Fortitude",
    type: "virtue",
    aliases: ["fortitude", "resilience", "inner strength", "endurance", "steadfast"],
    krishnaSaid: "Fortitude and forgiveness are divine qualities.",
    howToOvercome: "Stay with right action through difficulty without letting discomfort alone make the decision.",
    verse: "16.3",
    sloka: `tejaḥ kṣamā dhṛtiḥ śaucam
adroho nātimānitā
bhavanti sampadaṁ daivīm
abhijātasya bhārata`
  },

  {
    id: "serenity",
    label: "Serenity",
    type: "virtue",
    aliases: ["serene", "inner peace", "peace of mind", "quiet mind", "mental calm"],
    krishnaSaid: "Serenity, gentleness, self-control, and purity of thought are austerities of the mind.",
    howToOvercome: "Reduce mental clutter, simplify inputs, and deliberately cultivate thoughts that support clarity and goodwill.",
    verse: "17.16",
    sloka: `manaḥ-prasādaḥ saumyatvaṁ
maunam ātma-vinigrahaḥ
bhāva-saṁśuddhir ity etat
tapo mānasam ucyate`
  },

  {
    id: "truthfulness",
    label: "Truthfulness",
    type: "virtue",
    aliases: ["truth", "honest", "honesty", "speak truth", "sincere"],
    krishnaSaid: "Truthfulness is a divine quality.",
    howToOvercome: "Speak accurately and without manipulation while keeping the intention beneficial rather than cruel.",
    verse: "16.2",
    sloka: `ahiṁsā satyam akrodhas
tyāgaḥ śāntir apaiśunam
dayā bhūteṣv aloluptvaṁ
mārdavaṁ hrīr acāpalam`
  },

  {
    id: "gentleness",
    label: "Gentleness",
    type: "virtue",
    aliases: ["gentle", "soft spoken", "kind", "mild", "tender"],
    krishnaSaid: "Gentleness belongs to divine character.",
    howToOvercome: "Use strength without unnecessary harshness in speech, correction, and disagreement.",
    verse: "16.2",
    sloka: `ahiṁsā satyam akrodhas
tyāgaḥ śāntir apaiśunam
dayā bhūteṣv aloluptvaṁ
mārdavaṁ hrīr acāpalam`
  },

  {
    id: "nonviolence",
    label: "Nonviolence",
    type: "virtue",
    aliases: ["nonviolent", "do no harm", "peaceful", "avoid hurting", "ahimsa"],
    krishnaSaid: "Nonviolence is a divine quality.",
    howToOvercome: "Avoid causing unnecessary harm or agitation while still acting firmly when duty requires it.",
    verse: "16.2",
    sloka: `ahiṁsā satyam akrodhas
tyāgaḥ śāntir apaiśunam
dayā bhūteṣv aloluptvaṁ
mārdavaṁ hrīr acāpalam`
  },

  {
    id: "money_obsession",
    label: "Money Obsession",
    type: "material",
    aliases: ["money stress", "obsessed with money", "wealth obsession", "always thinking about money", "rich"],
    krishnaSaid: "Peace comes from reducing possessiveness, ego, and endless material desire.",
    howToOvercome: "Treat money as a tool and responsibility, not as the sole source of identity, security, or worth.",
    verse: "2.71",
    sloka: `vihāya kāmān yaḥ sarvān
pumāṁś carati niḥspṛhaḥ
nirmamo nirahaṅkāraḥ
sa śāntim adhigacchati`
  },

  {
    id: "covetousness",
    label: "Covetousness",
    type: "material",
    aliases: ["covetous", "want what others have", "material envy", "craving possessions", "greedy"],
    krishnaSaid: "Freedom from covetousness is a divine quality.",
    howToOvercome: "Reduce comparison-driven wanting and distinguish real need from desire created by seeing what others possess.",
    verse: "16.2",
    sloka: `ahiṁsā satyam akrodhas
tyāgaḥ śāntir apaiśunam
dayā bhūteṣv aloluptvaṁ
mārdavaṁ hrīr acāpalam`
  },

  {
    id: "fear_of_loss",
    label: "Fear of Loss",
    type: "material",
    aliases: ["afraid to lose", "loss anxiety", "scared of losing money", "possessive", "fear of losing"],
    krishnaSaid: "Do not be ruled by craving, lamentation, attraction, or aversion.",
    howToOvercome: "Prepare responsibly for loss, but do not let possessions become the foundation of inner stability.",
    verse: "12.17",
    sloka: `yo na hṛṣyati na dveṣṭi
na śocati na kāṅkṣati
śubhāśubha-parityāgī
bhaktimān yaḥ sa me priyaḥ`
  },

  {
    id: "material_comparison",
    label: "Material Comparison",
    type: "material",
    aliases: ["compare wealth", "compare salary", "compare possessions", "they have more", "status comparison"],
    krishnaSaid: "The self-controlled person is not spiritually defined by material value.",
    howToOvercome: "Use material differences practically, but do not use them as a measure of human worth.",
    verse: "6.8",
    sloka: `jñāna-vijñāna-tṛptātmā
kūṭa-stho vijitendriyaḥ
yukta ity ucyate yogī
sama-loṣṭrāśma-kāñcanaḥ`
  },

  {
    id: "loss",
    label: "Loss",
    type: "adversity",
    aliases: ["lost something", "lost someone", "setback", "something taken away", "grieving loss"],
    krishnaSaid: "Do not become consumed by lamentation or craving over changing circumstances.",
    howToOvercome: "Accept what cannot be recovered, act wisely with what remains, and avoid turning loss into your permanent identity.",
    verse: "12.17",
    sloka: `yo na hṛṣyati na dveṣṭi
na śocati na kāṅkṣati
śubhāśubha-parityāgī
bhaktimān yaḥ sa me priyaḥ`
  },

  {
    id: "unexpected_change",
    label: "Unexpected Change",
    type: "adversity",
    aliases: ["sudden change", "things changed", "unexpected event", "uncertainty", "life changed"],
    krishnaSaid: "Pleasure and pain arise and pass like changing seasons.",
    howToOvercome: "Stabilize first, remember that the present condition is not permanent, then adapt your next action.",
    verse: "2.14",
    sloka: `mātrā-sparśās tu kaunteya
śītoṣṇa-sukha-duḥkha-dāḥ
āgamāpāyino 'nityās
tāṁs titikṣasva bhārata`
  },

  {
    id: "pain",
    label: "Pain",
    type: "adversity",
    aliases: ["painful", "suffering", "hurt", "difficulty", "misery"],
    krishnaSaid: "A steady mind is not destroyed by distress.",
    howToOvercome: "Do what can reduce the suffering, but protect your judgment and identity from being completely swallowed by the pain.",
    verse: "2.56",
    sloka: `duḥkheṣv anudvigna-manāḥ
sukheṣu vigata-spṛhaḥ
vīta-rāga-bhaya-krodhaḥ
sthita-dhīr munir ucyate`
  },

  {
    id: "rejection",
    label: "Rejection",
    type: "adversity",
    aliases: ["rejected", "not selected", "turned down", "unwanted", "excluded"],
    krishnaSaid: "Praise and blame, honor and dishonor are changing external conditions.",
    howToOvercome: "Learn from the rejection where useful, but do not use another person's decision as the final verdict on your worth.",
    verse: "12.19",
    sloka: `tulya-nindā-stutir maunī
santuṣṭo yena kenacit
aniketaḥ sthira-matir
bhaktimān me priyo naraḥ`
  },

  {
    id: "uncertainty",
    label: "Uncertainty",
    type: "adversity",
    aliases: ["uncertain", "unknown future", "not sure what happens", "lack of control", "ambiguous"],
    krishnaSaid: "Your authority is over action, not guaranteed results.",
    howToOvercome: "Identify what is actually under your control today and act there instead of demanding certainty first.",
    verse: "2.47",
    sloka: `karmaṇy evādhikāras te
mā phaleṣu kadācana
mā karma-phala-hetur bhūr
mā te saṅgo 'stv akarmaṇi`
  },

  {
    id: "feeling_stuck",
    label: "Feeling Stuck",
    type: "adversity",
    aliases: ["stuck", "cannot move forward", "trapped", "no progress", "lost direction"],
    krishnaSaid: "Use the mind to elevate yourself rather than allowing it to pull you downward.",
    howToOvercome: "Stop trying to solve the entire future at once; choose one constructive action that changes your current direction.",
    verse: "6.5",
    sloka: `uddhared ātmanātmānaṁ
nātmānam avasādayet
ātmaiva hy ātmano bandhur
ātmaiva ripur ātmanaḥ`
  }
] as const satisfies readonly TraitExplanation[];
