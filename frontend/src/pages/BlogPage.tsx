import React from 'react';
import { Link } from 'react-router-dom';
import SEOHead from '../components/SEOHead';
import Logo from '../assets/logo.svg';
import './BlogPage.css';

// Sample blog posts - in production, these would come from a CMS or database
const blogPosts = [
  {
    id: 'first-time-buyer-checklist',
    title: "First-Time Home Buyer's Complete Checklist",
    excerpt: "Everything you need to know before buying your first home. From pre-approval to closing, we've got you covered.",
    category: 'Guide',
    date: '2026-02-01',
    readTime: '8 min read',
    image: '/blog/checklist.jpg',
  },
  {
    id: 'red-flags-real-estate',
    title: "Red Flags in Real Estate Listings (With Examples)",
    excerpt: "Learn to spot the warning signs in property listings that could save you from a costly mistake.",
    category: 'Tips',
    date: '2026-01-28',
    readTime: '6 min read',
    image: '/blog/red-flags.jpg',
  },
  {
    id: 'understanding-school-ratings',
    title: "Understanding School Ratings: What the Numbers Really Mean",
    excerpt: "School ratings can make or break a home purchase. Here's how to interpret them like a pro.",
    category: 'Education',
    date: '2026-01-20',
    readTime: '5 min read',
    image: '/blog/schools.jpg',
  },
  {
    id: 'ai-changing-home-buying',
    title: "How AI is Changing Home Buying in 2026",
    excerpt: "Discover how artificial intelligence is revolutionizing the way we analyze and purchase homes.",
    category: 'Industry',
    date: '2026-01-15',
    readTime: '7 min read',
    image: '/blog/ai-home.jpg',
  },
  {
    id: 'home-inspection-guide',
    title: "What to Look for in a Home Inspection Report",
    excerpt: "A comprehensive guide to understanding your home inspection report and which issues matter most.",
    category: 'Guide',
    date: '2026-01-10',
    readTime: '10 min read',
    image: '/blog/inspection.jpg',
  },
  {
    id: 'investment-property-analysis',
    title: "Analyzing Investment Properties: ROI, Cap Rate, and More",
    excerpt: "Master the key metrics that real estate investors use to evaluate rental properties.",
    category: 'Investment',
    date: '2026-01-05',
    readTime: '9 min read',
    image: '/blog/investment.jpg',
  },
];

const categories = ['All', 'Guide', 'Tips', 'Education', 'Industry', 'Investment'];

const BlogPage: React.FC = () => {
  const [selectedCategory, setSelectedCategory] = React.useState('All');

  const filteredPosts = selectedCategory === 'All'
    ? blogPosts
    : blogPosts.filter(post => post.category === selectedCategory);

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'long',
      day: 'numeric',
      year: 'numeric',
    });
  };

  return (
    <div className="blog-page">
      <SEOHead
        title="Blog - Perchspot"
        description="Home buying tips, market insights, and real estate analysis guides from Perchspot."
        path="/blog"
      />

      <header className="blog-header">
        <Link to="/" className="logo-link">
          <img src={Logo} alt="Perchspot" className="header-logo" />
        </Link>
        <nav className="blog-nav">
          <Link to="/">Home</Link>
          <Link to="/blog" className="active">Blog</Link>
        </nav>
      </header>

      <div className="blog-hero">
        <h1>Perchspot Blog</h1>
        <p>Home buying tips, market insights, and real estate analysis guides</p>
      </div>

      <div className="blog-content">
        <div className="category-filter">
          {categories.map(cat => (
            <button
              key={cat}
              className={`category-btn ${selectedCategory === cat ? 'active' : ''}`}
              onClick={() => setSelectedCategory(cat)}
            >
              {cat}
            </button>
          ))}
        </div>

        <div className="posts-grid">
          {filteredPosts.map(post => (
            <article key={post.id} className="post-card">
              <div className="post-image">
                <div className="post-image-placeholder">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" width="48" height="48">
                    <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
                    <polyline points="9,22 9,12 15,12 15,22"/>
                  </svg>
                </div>
              </div>
              <div className="post-content">
                <div className="post-meta">
                  <span className="post-category">{post.category}</span>
                  <span className="post-read-time">{post.readTime}</span>
                </div>
                <h2 className="post-title">
                  <Link to={`/blog/${post.id}`}>{post.title}</Link>
                </h2>
                <p className="post-excerpt">{post.excerpt}</p>
                <div className="post-footer">
                  <span className="post-date">{formatDate(post.date)}</span>
                  <Link to={`/blog/${post.id}`} className="read-more">
                    Read more
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="16" height="16">
                      <line x1="5" y1="12" x2="19" y2="12"/>
                      <polyline points="12,5 19,12 12,19"/>
                    </svg>
                  </Link>
                </div>
              </div>
            </article>
          ))}
        </div>

        {filteredPosts.length === 0 && (
          <div className="no-posts">
            <p>No posts found in this category.</p>
          </div>
        )}
      </div>

      <div className="blog-cta">
        <h2>Ready to analyze your next property?</h2>
        <p>Get AI-powered insights on any home in under 2 minutes.</p>
        <Link to="/" className="cta-btn">Try Perchspot Free</Link>
      </div>

      <footer className="blog-footer">
        <div className="footer-content">
          <Link to="/" className="footer-logo">
            <img src={Logo} alt="Perchspot" />
          </Link>
          <p>AI-Powered Property Analysis</p>
          <p className="copyright">© 2026 Perchspot. All rights reserved.</p>
        </div>
      </footer>
    </div>
  );
};

export default BlogPage;
