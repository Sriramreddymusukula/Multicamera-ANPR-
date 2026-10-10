import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { useGSAP } from '@gsap/react'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import { ArrowDown, ArrowRight, ArrowUpRight, Camera, Crosshair, Database, MapPin, Scan } from '@phosphor-icons/react'
import { api } from '../lib/api'
import { gsap } from '../lib/motion'
import { CameraMap } from '../components/MapView'
import '../styles/meridian.css'

gsap.registerPlugin(ScrollTrigger)

const number = (value) => typeof value === 'number' ? new Intl.NumberFormat('en-IN').format(value) : '—'
const steps = [
  ['DETECT', 'Find the signal.', 'YOLOv8 identifies number-plate regions in supported image and video input.'],
  ['READ', 'Make it legible.', 'OpenCV prepares the crop; Tesseract OCR extracts registration text.'],
  ['MATCH', 'Connect the sightings.', 'Compatible registration observations are associated across configured cameras.'],
  ['UNDERSTAND', 'See the pattern.', 'Operators review recorded histories, observed routes, and traffic activity summaries.'],
]
const showcases = [
  ['01 / ANPR CONSOLE', 'From footage to evidence.', 'Run image or video detection, review results, and save observations to the shared database.', '/console', 'Open ANPR Console'],
  ['02 / VEHICLE SEARCH', 'Follow a recorded history.', 'Look up a registration and inspect its observation timeline and camera sequence.', '/search', 'Explore Vehicle Search'],
  ['03 / MULTI-CAMERA TRACKING', 'See where sightings connect.', 'Review vehicles observed at more than one camera and open their reconstructed route.', '/tracking', 'Explore Tracking'],
  ['04 / NETWORK OVERVIEW', 'Activity, in context.', 'Explore aggregate camera counts, trends, and network geography.', '/overview', 'Open Network Overview'],
]

function Heading({ index, label, children, copy }) {
  return <div className="m-heading" data-reveal><span className="m-kicker">{index} / {label}</span><h2>{children}</h2>{copy && <p>{copy}</p>}</div>
}

function Preview({ type }) {
  return <div className={'m-preview m-preview--' + type} aria-label="Illustrative interface preview">
    <div className="m-preview__bar"><b>MERIDIAN</b><span>OPERATOR WORKSPACE</span><span>CAM-01 / CAM-04</span></div>
    {type === 'console' ? <div className="m-preview__console"><div className="m-preview__side">01<br />02<br />03</div><div className="m-preview__photo"><img src="/images/meridian-hero.webp" alt="" /><span>PLATE REGION / ILLUSTRATIVE</span></div><div className="m-preview__readout"><small>DETECTION PIPELINE</small><Scan size={38} /><strong>Image / video input</strong><span>Detect → Read → Record</span></div></div> : type === 'search' ? <div className="m-preview__search"><small>VEHICLE SEARCH / OPERATOR ACCESS</small><div>Enter a registration number <ArrowRight size={19} /></div><ol><li>CAM-01 <span>Recorded sighting</span></li><li>CAM-03 <span>Recorded sighting</span></li><li>CAM-04 <span>Recorded sighting</span></li></ol></div> : <div className="m-preview__network"><svg viewBox="0 0 600 260" aria-hidden="true"><path d="M70 190 C170 120 210 55 300 116 S450 215 535 60" /><circle cx="70" cy="190" r="7" /><circle cx="300" cy="116" r="7" /><circle cx="535" cy="60" r="7" /></svg><span>CAM-01</span><span>CAM-03</span><span>CAM-04</span><small>RECORDED OBSERVATION CORRELATION</small></div>}
  </div>
}

export function Meridian() {
  const root = useRef(null)
  const [data, setData] = useState({ summary: null, cameras: [], stats: [], error: false })
  const [selectedId, setSelectedId] = useState(null)
  useEffect(() => {
    let active = true
    Promise.all([api('/analytics/summary'), api('/cameras'), api('/analytics/cameras')])
      .then(([summary, cameras, stats]) => {
        if (active) setData({ summary, cameras: cameras.cameras, stats: stats.cameras, error: false })
      })
      .catch(() => { if (active) setData((old) => ({ ...old, error: true })) })
    return () => { active = false }
  }, [])
  useGSAP(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    gsap.timeline({ defaults: { ease: 'power3.out' } })
      .from('.m-hero__eyebrow', { y: 18, duration: .6 })
      .from('.m-hero h1 span', { y: 34, stagger: .13, duration: 1 }, '-=.25')
      .from('.m-hero__copy, .m-hero__actions', { y: 22, stagger: .12, duration: .7 }, '-=.5')
      .from('.m-detection', { y: 30, duration: .7 }, '-=.35')
    gsap.to('.m-hero__image', { yPercent: 10, ease: 'none', scrollTrigger: { trigger: '.m-hero', start: 'top top', end: 'bottom top', scrub: true } })
    gsap.utils.toArray('[data-reveal]', root.current).forEach((element) => gsap.from(element, { y: 30, autoAlpha: 0, duration: .8, ease: 'power2.out', scrollTrigger: { trigger: element, start: 'top 85%', once: true } }))
    const instrument = root.current.querySelector('.m-pipeline__instrument')
    gsap.utils.toArray('.m-pipeline__steps article', root.current).forEach((element, index) => {
      ScrollTrigger.create({
        trigger: element,
        start: 'top 55%',
        end: 'bottom 55%',
        onEnter: () => instrument?.setAttribute('data-step', String(index)),
        onEnterBack: () => instrument?.setAttribute('data-step', String(index)),
      })
    })
    gsap.fromTo('.m-pipeline__progress', { scaleX: 0 }, { scaleX: 1, ease: 'none', scrollTrigger: { trigger: '.m-pipeline__steps', start: 'top 55%', end: 'bottom 55%', scrub: true } })
  }, { scope: root })

  const { summary, cameras, stats, error } = data
  const selected = cameras.find((camera) => camera.id === selectedId) || cameras[0]
  const selectedStats = stats.find((row) => row.camera_id === selected?.id)
  const metrics = [['Network cameras', summary?.total_cameras], ['Recorded observations', summary?.total_observations], ['Unique observed vehicles', summary?.unique_vehicles], ['Cameras with observations', summary?.active_cameras]]

  return <div ref={root}>
    <section id="home" className="m-hero" aria-labelledby="m-hero-title">
      <div className="m-hero__image" role="img" aria-label="Illustrative Indian SUV on a rain-soaked Hyderabad road at night" /><div className="m-hero__shade" />
      <div className="m-hero__content"><p className="m-hero__eyebrow"><i /> A NEW PERSPECTIVE ON THE CITY</p><h1 id="m-hero-title"><span>Every road</span><span>tells a story.</span></h1><p className="m-hero__copy">A multi-camera vehicle intelligence platform that turns number-plate detections into real insights. Built for safer, smarter and more connected cities.</p><div className="m-hero__actions"><a className="m-button m-button--light" href="#platform">Explore the Platform <ArrowUpRight size={18} /></a><a className="m-text-link" href="#how-it-works">Discover How It Works <ArrowDown size={17} /></a></div></div>
      <div className="m-hero__platebox" aria-hidden="true" />
      <div className="m-detection" aria-label="Illustrative detection interface"><div><span>● DETECTION PREVIEW</span><span>ILLUSTRATIVE</span></div><strong><Scan size={22} /> REGISTRATION DETECTED</strong><section><span>CONFIDENCE <b>—</b></span><span>CAMERA ID <b>CAM-01</b></span><span>LOCATION <b>HYDERABAD</b></span><span>OBSERVED AT <b>—</b></span></section></div>
      <div className="m-hero__bottom"><span>MERIDIAN / CITY INTELLIGENCE</span><span>SCROLL TO EXPLORE <ArrowDown size={14} /></span></div>
    </section>
    <section className="m-stats" aria-label="Operational snapshot"><div className="m-stats__intro"><span className="m-kicker">OPERATIONAL SNAPSHOT</span><p>{error ? 'API unavailable — connect the backend to view network metrics.' : 'Current records from the configured simulated camera network.'}</p></div><div className="m-stats__row">{metrics.map(([label, value], index) => <div key={label} className="m-stat"><small>0{index + 1} / {label}</small><strong>{number(value)}</strong></div>)}</div></section>
    <section id="platform" className="m-intelligence m-section"><div className="m-container"><Heading index="01" label="CITY INTELLIGENCE" copy="A registration observed at separate cameras becomes a sequence of recorded sightings. Meridian connects those observations to help operators understand where a vehicle was seen across the configured network.">One city.<br /><em>Connected sightings.</em></Heading><div className="m-map-stage" data-reveal><div className="m-map-stage__map">{cameras.length ? <CameraMap cameras={cameras} stats={stats} selectedId={selected?.id} onSelect={setSelectedId} cityOverview tall /> : <div className="m-map-stage__empty">{error ? 'Map unavailable while the API is offline.' : 'Loading camera network…'}</div>}</div><div className="m-map-stage__panel"><span className="m-kicker">SIMULATED NETWORK / HYDERABAD</span><h3>Observe the network.</h3><p>Select a camera marker to inspect its configured location and aggregate recorded activity.</p><div className="m-map-stage__selected"><span><MapPin size={19} /> {selected?.id || '—'}</span><strong>{selected?.location || 'Awaiting network data'}</strong><small>{selectedStats ? number(selectedStats.observations) + ' recorded observations' : 'No recorded observations'}</small></div><div className="m-map-stage__camera-list">{cameras.map((camera) => <button key={camera.id} type="button" className={camera.id === selected?.id ? 'is-active' : ''} onClick={() => setSelectedId(camera.id)}>{camera.id}</button>)}</div></div><span className="m-map-stage__caption">INTERACTIVE HYDERABAD MAP · CONFIGURED CAMERA COORDINATES · RECORDED OBSERVATIONS ONLY</span></div><div className="m-journey" data-reveal><div><span className="m-kicker">FROM POINTS TO CONTEXT</span><h3>A journey is a set of observations, not a continuous feed.</h3></div><svg viewBox="0 0 800 110" preserveAspectRatio="none" aria-hidden="true"><path d="M38 75 C190 75 155 22 312 38 S520 94 601 45 S735 44 764 18" /><circle cx="38" cy="75" r="6" /><circle cx="312" cy="38" r="6" /><circle cx="601" cy="45" r="6" /><circle cx="764" cy="18" r="6" /></svg><span>CAMERA 01 → CAMERA 02 → CAMERA 03 → HISTORY · ILLUSTRATIVE</span></div></div></section>
    <section id="how-it-works" className="m-pipeline m-section">
      <div className="m-container">
        <div className="m-pipeline__intro" data-reveal>
          <span className="m-kicker">02 / HOW IT WORKS</span>
          <h2>From a moment on the road <br />to <em>meaningful context.</em></h2>
          <p>Four deliberate steps. One connected record of what the cameras actually observed.</p>
        </div>
        <div className="m-pipeline__layout">
          <div className="m-pipeline__sticky">
            <div className="m-pipeline__instrument" data-step="0" aria-label="Processing sequence illustration">
              <div className="m-pipeline__instrument-scan">
                <span className="m-pipeline__instrument-caption">ILLUSTRATIVE / OBSERVATION SEQUENCE</span>
              </div>
              <ol><li>01 / DETECT</li><li>02 / READ</li><li>03 / MATCH</li><li>04 / UNDERSTAND</li></ol>
              <div className="m-pipeline__rail"><span className="m-pipeline__progress" /></div>
            </div>
            <p className="m-pipeline__instrument-note">A sequence of recorded sightings, never a continuous live path.</p>
          </div>
          <div className="m-pipeline__steps">
            {steps.map(([label, title, copy], index) => <article key={label} data-reveal>
              <span>0{index + 1} / {label}</span>
              <div className={'m-step-visual m-step-visual--' + label.toLowerCase()}>
                {index === 0 ? <><img src="/images/meridian-hero.webp" alt="Illustrative Indian SUV on a city road" loading="lazy" /><span>PLATE REGION / ILLUSTRATIVE</span></> : index === 1 ? <><Scan size={70} /><ArrowRight size={26} /><strong>OCR<br />TEXT</strong></> : index === 2 ? <><span>CAM-01</span><i /><span>CAM-03</span><i /><span>CAM-04</span></> : <><Database size={54} /><strong>Observation → history → insight</strong></>}
              </div>
              <h3>{title}</h3><p>{copy}</p>
            </article>)}
          </div>
        </div>
      </div>
    </section>
    <section className="m-showcase m-section"><div className="m-container"><Heading index="03" label="THE PLATFORM" copy="The operational application gives authorized users tools to detect, search, and interpret recorded sightings.">A clearer view<br />of every observation.</Heading><div className="m-showcase__feature" data-reveal><div><span className="m-kicker">{showcases[0][0]}</span><h3>{showcases[0][1]}</h3><p>{showcases[0][2]}</p><Link to="/console">{showcases[0][4]} <ArrowUpRight size={18} /></Link></div><Preview type="console" /></div><div className="m-showcase__pair">{showcases.slice(1, 3).map(([label, title, copy, route, cta], index) => <article key={route} data-reveal><Preview type={index ? 'network' : 'search'} /><span className="m-kicker">{label}</span><h3>{title}</h3><p>{copy}</p><Link to={route}>{cta} <ArrowUpRight size={18} /></Link></article>)}</div><div className="m-showcase__overview" data-reveal><div><span className="m-kicker">{showcases[3][0]}</span><h3>{showcases[3][1]}</h3><p>{showcases[3][2]}</p><Link to="/overview">{showcases[3][4]} <ArrowUpRight size={18} /></Link></div><div className="m-showcase__bars" aria-hidden="true">{Array.from({ length: 12 }, (_, i) => <i key={i} />)}</div></div><p className="m-showcase__note">Interface previews are illustrative compositions based on existing features. They contain no real registration data.</p></div></section>
    <section id="technology" className="m-tech m-section"><div className="m-container"><Heading index="04" label="TECHNOLOGY" copy="Meridian presents the project's processing stack, from image input to persistent records and a protected operator workspace.">Intelligence, built<br />one layer at a time.</Heading><div className="m-tech__flow" data-reveal>{[[Camera, 'INPUT', 'Image & video'], [Crosshair, 'DETECTION', 'Python · YOLOv8'], [Scan, 'READING', 'OpenCV · Tesseract'], [Database, 'PERSISTENCE', 'CSV observations'], [ArrowUpRight, 'EXPERIENCE', 'FastAPI · React']].map(([Icon, label, name]) => <div key={label}><Icon size={28} /><span>{label}</span><strong>{name}</strong></div>)}</div><div className="m-tech__bottom"><p>Each observation is recorded with its camera, location, time, confidence, and evidence. Matching and analytics operate on those stored records.</p><span>NO CLAIM OF CONTINUOUS LIVE TRACKING</span></div></div></section>
    <section id="use-cases" className="m-uses m-section"><div className="m-container"><Heading index="05" label="USE CASES">Built for the questions<br />a city actually asks.</Heading><div className="m-uses__list">{[['Traffic observation & analysis', 'Understand recorded activity by camera and over time.'], ['Vehicle sighting investigation', 'Search authorized records for where and when a registration was observed.'], ['Multi-camera correlation', 'Associate compatible sightings across configured junctions.'], ['Network activity insights', 'Compare aggregate observations and identify patterns in the available data.']].map(([title, copy], index) => <article key={title} data-reveal><span>0{index + 1}</span><h3>{title}</h3><p>{copy}</p><ArrowUpRight size={23} /></article>)}</div></div></section>
    <section id="about" className="m-final"><div className="m-final__image" /><div className="m-container m-final__content"><span className="m-kicker">MERIDIAN / CITY INTELLIGENCE</span><h2>See the city<br /><em>differently.</em></h2><p>Explore what connected number-plate observations can reveal about the roads we share.</p><Link className="m-button m-button--light" to="/console">Launch Console <ArrowUpRight size={19} /></Link></div></section>
    <footer className="m-footer"><div className="m-container"><div className="m-footer__top"><div><strong>MERIDIAN</strong><span>CITY INTELLIGENCE</span><p>Every road tells a story.</p></div><div><span>EXPLORE</span><a href="#platform">Platform</a><a href="#how-it-works">How it works</a><a href="#technology">Technology</a><a href="#use-cases">Use Cases</a></div><div><span>APPLICATION</span><Link to="/console">ANPR Console</Link><Link to="/search">Vehicle Search</Link><Link to="/tracking">Multi-Camera Tracking</Link><Link to="/overview">Network Overview</Link></div></div><div className="m-footer__bottom"><p>Prototype using a simulated Hyderabad camera network. Observed routes are reconstructed from recorded detections, not continuous live tracking. Public pages show aggregate data only.</p><span>MERIDIAN · CITY INTELLIGENCE</span></div></div></footer>
  </div>
}
