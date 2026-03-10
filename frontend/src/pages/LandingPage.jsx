import { useState } from 'react';
import { motion } from 'framer-motion';
import { Video, Bot, Code, ArrowRight, Zap, Target, ShieldCheck, Mail, ChevronRight, PlayCircle } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

export default function LandingPage() {
    const [isContactOpen, setIsContactOpen] = useState(false);
    const navigate = useNavigate();

    // Staggered animation settings
    const container = {
        hidden: { opacity: 0 },
        show: {
            opacity: 1,
            transition: {
                staggerChildren: 0.2
            }
        }
    };

    const item = {
        hidden: { opacity: 0, y: 30 },
        show: { opacity: 1, y: 0, transition: { duration: 0.6, ease: "easeOut" } }
    };

    return (
        <div className="min-h-screen bg-[#030614] text-slate-100 font-sans selection:bg-indigo-500/30 overflow-x-hidden">
            {/* Ambient Background Glow */}
            <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[500px] bg-indigo-600/20 blur-[150px] rounded-full pointer-events-none" />

            {/* Navbar */}
            <nav className="relative z-50 flex items-center justify-between px-6 py-6 max-w-7xl mx-auto">
                <div className="flex items-center gap-2 cursor-pointer">
                    <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center">
                        <Zap size={18} className="text-white" fill="currentColor" />
                    </div>
                    <span className="text-xl font-bold tracking-tight text-white">Neural Knights</span>
                </div>
                <div className="hidden md:flex items-center gap-8 text-sm font-medium text-slate-400">
                    <a href="#products" className="hover:text-white transition-colors">Products</a>
                    <a href="#about" className="hover:text-white transition-colors">About Us</a>
                    <button onClick={() => setIsContactOpen(true)} className="hover:text-white transition-colors">Contact</button>
                    <button
                        onClick={() => navigate("/login")}
                        className="px-4 py-2 rounded-full bg-slate-800 border border-slate-700 hover:bg-slate-700 text-white transition-all shadow-lg"
                    >
                        Login
                    </button>
                </div>
            </nav>

            {/* Hero Section */}
            <section className="relative z-10 pt-20 pb-32 px-6 max-w-7xl mx-auto text-center flex flex-col items-center">
                <motion.div initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.7 }}>
                    <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-300 text-xs font-semibold uppercase tracking-wider mb-8">
                        <span className="w-2 h-2 rounded-full bg-indigo-500 animate-pulse" />
                        Pioneering the Future of AI Software
                    </div>
                    <h1 className="text-5xl md:text-7xl font-extrabold tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-white block via-slate-200 to-slate-500 leading-tight mb-6">
                        Automate. Generate. <br /> Dominate.
                    </h1>
                    <p className="text-lg md:text-xl text-slate-400 max-w-2xl mx-auto mb-10 leading-relaxed">
                        Neural Knights provides elite AI infrastructure. From cinematic video generation to autonomous WhatsApp sales agents and custom enterprise development.
                    </p>
                    <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
                        <a href="#products" className="group flex items-center justify-center gap-2 px-8 py-3.5 rounded-full bg-white text-black font-semibold hover:bg-slate-200 transition-all shadow-[0_0_30px_rgba(255,255,255,0.2)]">
                            Explore Products
                            <ArrowRight size={18} className="group-hover:translate-x-1 transition-transform" />
                        </a>
                        <button onClick={() => setIsContactOpen(true)} className="flex items-center justify-center gap-2 px-8 py-3.5 rounded-full bg-transparent border border-slate-700 text-white font-semibold hover:bg-slate-800 transition-all">
                            Talk to enterprise
                        </button>
                    </div>
                </motion.div>
            </section>

            {/* Three Pillars Section */}
            <section id="products" className="relative z-10 py-24 px-6 bg-slate-900/40 border-y border-slate-800/50">
                <div className="max-w-7xl mx-auto">
                    <div className="text-center mb-16">
                        <h2 className="text-3xl md:text-4xl font-bold mb-4">Our Ecosystem</h2>
                        <p className="text-slate-400">Everything you need to scale your business using cutting-edge AI architecture.</p>
                    </div>

                    <motion.div
                        variants={container}
                        initial="hidden"
                        whileInView="show"
                        viewport={{ once: true, margin: "-100px" }}
                        className="grid md:grid-cols-3 gap-6"
                    >
                        {/* Service 1: Catalyst Nexus Core */}
                        <motion.div variants={item} className="group relative flex flex-col p-8 rounded-3xl bg-slate-900/80 border border-slate-800 hover:border-indigo-500/50 transition-all overflow-hidden cursor-pointer" onClick={() => navigate("/campaigns")}>
                            <div className="absolute inset-0 bg-gradient-to-br from-indigo-500/5 to-purple-500/5 opacity-0 group-hover:opacity-100 transition-opacity" />
                            <div className="w-14 h-14 rounded-2xl bg-indigo-500/20 flex items-center justify-center mb-6 ring-1 ring-indigo-500/30">
                                <Video size={28} className="text-indigo-400" />
                            </div>
                            <h3 className="text-2xl font-bold mb-3 text-white">Content Engine</h3>
                            <p className="text-slate-400 leading-relaxed mb-6 flex-1">
                                Generative AI for cinematic video campaigns, AI market scouting, deep trend research, and automated DALL-E 3 poster generation.
                            </p>
                            <span className="flex items-center font-semibold text-indigo-400 mt-auto group-hover:gap-2 transition-all gap-1">
                                Launch App <ChevronRight size={18} />
                            </span>
                        </motion.div>

                        {/* Service 2: Catalyst Plugins (WhatsApp) */}
                        <motion.div variants={item} className="group relative flex flex-col p-8 rounded-3xl bg-slate-900/80 border border-slate-800 hover:border-emerald-500/50 transition-all overflow-hidden cursor-pointer" onClick={() => navigate("/whatsapp-bot")}>
                            <div className="absolute inset-0 bg-gradient-to-br from-emerald-500/5 to-teal-500/5 opacity-0 group-hover:opacity-100 transition-opacity" />
                            <div className="w-14 h-14 rounded-2xl bg-emerald-500/20 flex items-center justify-center mb-6 ring-1 ring-emerald-500/30">
                                <Bot size={28} className="text-emerald-400" />
                            </div>
                            <h3 className="text-2xl font-bold mb-3 text-white">AI Business Agent</h3>
                            <p className="text-slate-400 leading-relaxed mb-6 flex-1">
                                Mount an autonomous AI on your WhatsApp. Instantly read user intents, check Google Calendar slots, and secure bookings for your local business without lifting a finger.
                            </p>
                            <span className="flex items-center font-semibold text-emerald-400 mt-auto group-hover:gap-2 transition-all gap-1">
                                Configure Bot <ChevronRight size={18} />
                            </span>
                        </motion.div>

                        {/* Service 3: Custom Dev */}
                        <motion.div variants={item} className="group relative flex flex-col p-8 rounded-3xl bg-slate-900/80 border border-slate-800 hover:border-orange-500/50 transition-all overflow-hidden cursor-pointer" onClick={() => setIsContactOpen(true)}>
                            <div className="absolute inset-0 bg-gradient-to-br from-orange-500/5 to-amber-500/5 opacity-0 group-hover:opacity-100 transition-opacity" />
                            <div className="w-14 h-14 rounded-2xl bg-orange-500/20 flex items-center justify-center mb-6 ring-1 ring-orange-500/30">
                                <Code size={28} className="text-orange-400" />
                            </div>
                            <h3 className="text-2xl font-bold mb-3 text-white">Bespoke Enterprise</h3>
                            <p className="text-slate-400 leading-relaxed mb-6 flex-1">
                                Don't see what you need? We architect custom LLM infrastructures, RAG pipelines, and automated agentic systems tailored exclusively for your enterprise.
                            </p>
                            <span className="flex items-center font-semibold text-orange-400 mt-auto group-hover:gap-2 transition-all gap-1">
                                Request Proposal <ChevronRight size={18} />
                            </span>
                        </motion.div>
                    </motion.div>
                </div>
            </section>

            {/* Why Us Section */}
            <section id="about" className="relative z-10 py-24 px-6 max-w-7xl mx-auto">
                <div className="flex flex-col md:flex-row gap-16 items-center">
                    <div className="flex-1">
                        <h2 className="text-3xl md:text-5xl font-bold mb-6 leading-tight">Beyond Wrappers.<br /><span className="text-slate-500">True Engineering.</span></h2>
                        <p className="text-slate-400 text-lg mb-8 leading-relaxed">
                            Neural Knights actively builds heavy, decoupled async environments. Our Graph Neural Networks predict trends before they happen, while our decentralized plugin architectures ensure absolute API isolation and zero downtime.
                        </p>
                        <div className="space-y-4">
                            <div className="flex items-start gap-4">
                                <div className="mt-1 p-1 bg-indigo-500/20 rounded-lg"><Target size={18} className="text-indigo-400" /></div>
                                <div>
                                    <h4 className="font-semibold text-white">Precision Algorithms</h4>
                                    <p className="text-sm text-slate-400">Not just chat bots. We execute multi-stage autonomous reasoning graphs.</p>
                                </div>
                            </div>
                            <div className="flex items-start gap-4">
                                <div className="mt-1 p-1 bg-indigo-500/20 rounded-lg"><ShieldCheck size={18} className="text-indigo-400" /></div>
                                <div>
                                    <h4 className="font-semibold text-white">Headless Architecture</h4>
                                    <p className="text-sm text-slate-400">Strict separation of Central AI Generation and Delivery Mechanisms for massive scalability.</p>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div className="flex-1 w-full relative">
                        <div className="aspect-square md:aspect-video rounded-3xl border border-slate-700 bg-slate-900/50 flex items-center justify-center overflow-hidden relative shadow-2xl">
                            <div className="absolute inset-0 bg-gradient-to-tr from-indigo-500/10 to-purple-500/10 mix-blend-overlay" />
                            {/* Abstract decorative interface inside */}
                            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[80%] h-[60%] border border-slate-800 rounded-xl bg-slate-950/80 p-4 shadow-lg backdrop-blur flex flex-col gap-3">
                                <div className="h-4 w-1/3 bg-slate-800 rounded-lg animate-pulse" />
                                <div className="h-2 w-full bg-slate-800 rounded-lg" />
                                <div className="h-2 w-3/4 bg-slate-800 rounded-lg" />
                                <div className="mt-auto flex justify-between">
                                    <div className="h-8 w-1/4 bg-indigo-500/30 rounded-lg" />
                                    <div className="h-8 w-8 rounded-full bg-emerald-500/30" />
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </section>

            {/* Footer / CTA */}
            <footer className="relative py-12 px-6 border-t border-slate-800/50 text-center">
                <span className="text-slate-500 text-sm font-medium">&copy; {new Date().getFullYear()} Neural Knights. Accelerating the future.</span>
            </footer>

            {/* Custom Contact Modal */}
            {isContactOpen && (
                <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
                    <motion.div
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ opacity: 1, scale: 1 }}
                        className="w-full max-w-lg bg-slate-900 border border-slate-700/50 rounded-3xl p-8 shadow-2xl relative"
                    >
                        <button onClick={() => setIsContactOpen(false)} className="absolute top-6 right-6 text-slate-400 hover:text-white">✕</button>
                        <div className="w-12 h-12 bg-white flex items-center justify-center rounded-2xl mb-6 shadow-[0_0_20px_rgba(255,255,255,0.1)]">
                            <Mail size={24} className="text-black" />
                        </div>
                        <h3 className="text-2xl font-bold mb-2">Request Custom Development</h3>
                        <p className="text-slate-400 mb-8">Discuss your enterprise AI vision with our architecture team.</p>

                        <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); alert("Feature coming soon!"); setIsContactOpen(false); }}>
                            <div>
                                <label className="block text-sm font-medium text-slate-400 mb-1">Company / Name</label>
                                <input required type="text" className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none text-white transition-all" placeholder="Acme Corp" />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-slate-400 mb-1">Email</label>
                                <input required type="email" className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none text-white transition-all" placeholder="founder@acmecorp.com" />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-slate-400 mb-1">Project Brief</label>
                                <textarea required rows={4} className="w-full bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none text-white transition-all resize-none" placeholder="We need an AI agent that can..." />
                            </div>
                            <button type="submit" className="w-full bg-white text-black font-semibold rounded-xl py-3 hover:bg-slate-200 transition-colors mt-2">
                                Send Request
                            </button>
                        </form>
                    </motion.div>
                </div>
            )}
        </div>
    );
}
