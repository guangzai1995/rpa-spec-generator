import React from 'react';
import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom';
import HomePage from './pages/HomePage';
import SettingsPage from './pages/SettingsPage';

function Header() {
  const location = useLocation();
  return (
    <header className="header">
      <div className="header-brand">
        <div className="header-logo">R</div>
        <h1>RPA 需求规格说明书生成</h1>
      </div>
      <nav>
        <Link to="/" className={location.pathname === '/' ? 'active' : ''}>
          首页
        </Link>
        <Link to="/settings" className={location.pathname === '/settings' ? 'active' : ''}>
          设置
        </Link>
      </nav>
    </header>
  );
}

function App() {
  return (
    <BrowserRouter>
      <div className="app">
        <Header />
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}

export default App;
