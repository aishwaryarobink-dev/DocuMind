import './App.scss';

export default function App(){
    return(
        <div className="root">
            <header className="topbar">
                <span className="logo">DocuMind</span>
                <span className="badge">Day 1 - setup Complete</span>
            </header>
            <div className="body"  >
                <aside className="panel">
                    <p className="panelText">Files Panel goes here</p>
                </aside>
                <main className="main">
                    <p className="mainText">Chat area goes here</p>
                </main>
            </div>
            
        </div>
    )
}