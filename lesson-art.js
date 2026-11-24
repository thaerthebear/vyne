'use strict';
(()=>{
 const base=new URL('.',document.currentScript?.src||location.href);
 const lessons={
 "0.1": {
  "title": "Your Roadmap",
  "caption": "Turn lessons into a working rental process.",
  "alt": "A blue road connects a planning clipboard, rental car, keys and a finished receipt.",
  "asset": "assets/lessons/lesson-0-1-v1.jpg"
 },
 "0.2": {
  "title": "Choose Your Starting Point",
  "caption": "Start where you are. Find your next gap.",
  "alt": "Two starting paths, one with a first key and one with a small fleet, join a shared checklist.",
  "asset": "assets/lessons/lesson-0-2-v1.jpg"
 },
 "1.1": {
  "title": "Choose Your Target Customer",
  "caption": "Choose the customer before choosing the car.",
  "alt": "A magnifying glass selects a commuter briefcase beside a rental car, with other customer needs in the background.",
  "asset": "assets/lessons/lesson-1-1-v1.jpg"
 },
 "1.2": {
  "title": "Research Your Local Market",
  "caption": "Compare the whole offer on equal terms.",
  "alt": "Three matching rental cars sit above different receipts beside a magnifying glass.",
  "asset": "assets/lessons/lesson-1-2-v1.jpg"
 },
 "1.3": {
  "title": "Choose Your Operating Model",
  "caption": "Decide who owns each responsibility.",
  "alt": "A rental car connects to three distinct stations for the owner, operator and written arrangement.",
  "asset": "assets/lessons/lesson-1-3-v1.jpg"
 },
 "1.4": {
  "title": "Understand Your Costs",
  "caption": "See where your rental income goes.",
  "alt": "A stack of rental income is separated into tools, recurring bills and a smaller remaining coin stack.",
  "asset": "assets/lessons/lesson-1-4-v1.jpg"
 },
 "1.5": {
  "title": "Build Your Business Plan",
  "caption": "Bring your research into one useful plan.",
  "alt": "A customer briefcase, rental car, coins and calendar fit around a single planning page.",
  "asset": "assets/lessons/lesson-1-5-v1.jpg"
 },
 "2.1": {
  "title": "Choose Vehicles for Your Market",
  "caption": "Match the vehicle to the job.",
  "alt": "A compact car, roomy SUV and cargo van are paired with a briefcase, stroller and boxes.",
  "asset": "assets/lessons/lesson-2-1-v1.jpg"
 },
 "2.2": {
  "title": "Evaluate a Vehicle Before Committing",
  "caption": "Look beyond a clean exterior.",
  "alt": "A rental car is examined with a magnifying glass, service folder and inspection light.",
  "asset": "assets/lessons/lesson-2-2-v1.jpg"
 },
 "2.3": {
  "title": "Evaluate Purchase, Financing, Lease, or Partnership Options",
  "caption": "Compare the full commitment.",
  "alt": "Four paths to one vehicle show upfront money, installments, a timed key and shared responsibility.",
  "asset": "assets/lessons/lesson-2-3-v1.jpg"
 },
 "2.4": {
  "title": "Prepare a Vehicle for Rental",
  "caption": "Ready means checked, recorded and equipped.",
  "alt": "A rental car is surrounded by cleaning supplies, tools, two keys and a condition-photo camera.",
  "asset": "assets/lessons/lesson-2-4-v1.jpg"
 },
 "3.1": {
  "title": "Organize Your Business Setup",
  "caption": "Build a checklist for your actual location.",
  "alt": "A location pin anchors a business folder with separate tabs and a checklist.",
  "asset": "assets/lessons/lesson-3-1-v1.jpg"
 },
 "3.2": {
  "title": "Understand Your Insurance Needs",
  "caption": "Verify what the policy actually covers.",
  "alt": "An open policy folder is examined through a magnifying glass beside a rental car and a question-shaped object.",
  "asset": "assets/lessons/lesson-3-2-v1.jpg"
 },
 "3.3": {
  "title": "Set Renter and Driver Requirements",
  "caption": "Use consistent checks for every driver.",
  "alt": "Two anonymous driver cards pass through the same checklist beside a car key.",
  "asset": "assets/lessons/lesson-3-3-v1.jpg"
 },
 "3.4": {
  "title": "Prepare and Review Your Agreements",
  "caption": "Review the agreement before filling it in.",
  "alt": "A document is matched to a car, calendar and rental details under a magnifying glass.",
  "asset": "assets/lessons/lesson-3-4-v1.jpg"
 },
 "3.5": {
  "title": "Write Clear Rental Policies",
  "caption": "Make the rules clear before problems happen.",
  "alt": "A tidy policy booklet organizes icons for fuel, time, distance and cancellation.",
  "asset": "assets/lessons/lesson-3-5-v1.jpg"
 },
 "4.1": {
  "title": "Create a Trustworthy Brand and Listing",
  "caption": "Show what the renter will really receive.",
  "alt": "A phone listing shows a clear rental-car photo beside the same real car and an inspection camera.",
  "asset": "assets/lessons/lesson-4-1-v1.jpg"
 },
 "4.2": {
  "title": "Set and Review Your Pricing",
  "caption": "Price for your costs and paid rental days.",
  "alt": "A balanced scale compares a rental car and calendar with costs and a small coin stack.",
  "asset": "assets/lessons/lesson-4-2-v1.jpg"
 },
 "4.3": {
  "title": "Build Your Customer Acquisition Plan",
  "caption": "Test one channel and measure useful inquiries.",
  "alt": "Three possible customer channels narrow to one selected path toward a rental booking.",
  "asset": "assets/lessons/lesson-4-3-v1.jpg"
 },
 "4.4": {
  "title": "Turn Inquiries into Bookings",
  "caption": "Guide an inquiry through the booking steps.",
  "alt": "A question bubble moves through a calendar and quote to a reserved car key.",
  "asset": "assets/lessons/lesson-4-4-v1.jpg"
 },
 "5.1": {
  "title": "Review the Reservation",
  "caption": "Match every reservation detail before pickup.",
  "alt": "A calendar, car key and driver card align with one central reservation record.",
  "asset": "assets/lessons/lesson-5-1-v1.jpg"
 },
 "5.2": {
  "title": "Complete the Agreement",
  "caption": "Track the signature, then keep the evidence.",
  "alt": "A stylus signs a document while matching completed paperwork is filed beside a rental key.",
  "asset": "assets/lessons/lesson-5-2-v1.jpg"
 },
 "5.3": {
  "title": "Confirm Payment and Deposit Status",
  "caption": "Confirm payment and deposit separately.",
  "alt": "Two separate payment trays show rental payment and a protected refundable deposit beside a terminal.",
  "asset": "assets/lessons/lesson-5-3-v1.jpg"
 },
 "5.4": {
  "title": "Complete Pickup and Vehicle Handoff",
  "caption": "Record the condition before handing over keys.",
  "alt": "A phone photographs a car while two people review the vehicle and a key waits on the clipboard.",
  "asset": "assets/lessons/lesson-5-4-v1.jpg"
 },
 "5.5": {
  "title": "Manage the Active Rental",
  "caption": "Record a change before extending the trip.",
  "alt": "A message bubble and requested extra calendar day wait beside an active rental car.",
  "asset": "assets/lessons/lesson-5-5-v1.jpg"
 },
 "5.6": {
  "title": "Complete the Return and Closeout",
  "caption": "Compare pickup and return before closeout.",
  "alt": "Two matching vehicle photos are compared beside returned keys and a receipt.",
  "asset": "assets/lessons/lesson-5-6-v1.jpg"
 },
 "6.1": {
  "title": "Handle Cancellations, No-Shows, and Late Returns",
  "caption": "Use the timeline and policy when plans change.",
  "alt": "A calendar tile is moved beside a clock, message record and policy folder.",
  "asset": "assets/lessons/lesson-6-1-v1.jpg"
 },
 "6.2": {
  "title": "Respond to Breakdowns, Accidents, and Damage Reports",
  "caption": "Safety first. Then help and records.",
  "alt": "A stopped rental car has a warning triangle, assistance phone and evidence folder nearby.",
  "asset": "assets/lessons/lesson-6-2-v1.jpg"
 },
 "6.3": {
  "title": "Resolve Payment Issues and Customer Complaints",
  "caption": "Organize the facts before deciding a response.",
  "alt": "Two conversation bubbles meet above an organized folder of photos, agreement and receipt.",
  "asset": "assets/lessons/lesson-6-3-v1.jpg"
 },
 "7.1": {
  "title": "Review Your Business Performance",
  "caption": "Review results, not just a busy calendar.",
  "alt": "A calendar, coin trays and downtime tool are examined beside a simple business chart.",
  "asset": "assets/lessons/lesson-7-1-v1.jpg"
 },
 "7.2": {
  "title": "Plan Maintenance and Vehicle Replacement",
  "caption": "Reserve time for service before taking bookings.",
  "alt": "A service wrench occupies a blocked calendar day beside a rental car and maintenance folder.",
  "asset": "assets/lessons/lesson-7-2-v1.jpg"
 },
 "7.3": {
  "title": "Build Your Team and Daily Procedures",
  "caption": "Give every task an owner and a handoff.",
  "alt": "Three team stations pass a checklist from booking to handoff to return inspection.",
  "asset": "assets/lessons/lesson-7-3-v1.jpg"
 },
 "7.4": {
  "title": "Decide When to Expand",
  "caption": "Expand after the current process proves ready.",
  "alt": "One solid rental-car platform supports a proposed second vehicle with checks still to review.",
  "asset": "assets/lessons/lesson-7-4-v1.jpg"
 }
};
 function info(id){const row=lessons[id];if(!row)throw Error('Missing lesson illustration: '+id);return row}
 function url(id){return new URL(info(id).asset,base).href}
 function image(id,{eager=false,decorative=false}={}){const row=info(id),img=document.createElement('img');img.src=url(id);img.alt=decorative?'':row.alt;img.width=960;img.height=640;img.loading=eager?'eager':'lazy';img.decoding='async';img.dataset.artLesson=id;return img}
 function figure(id){const box=document.createElement('figure');box.className='lesson-illustration';box.append(image(id));const caption=document.createElement('figcaption');caption.textContent=info(id).caption;box.append(caption);return box}
 function thumbnail(button,id,title){const label=document.createElement('span');label.className='lesson-link-title';label.textContent=title;button.replaceChildren(image(id,{decorative:true}),label)}
 function hero(box,id){if(box.dataset.artLesson===id)return;box.classList.add('lesson-hero-art');box.classList.remove('training-preview');box.removeAttribute('role');box.removeAttribute('aria-label');box.replaceChildren(image(id,{eager:true}));box.dataset.artLesson=id}
 window.RycfLessonArt={info,url,image,figure,thumbnail,hero};
})();
