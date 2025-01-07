from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_login import LoginManager, login_required, current_user
from werkzeug.utils import secure_filename
from datetime import datetime, timezone
import os
from models import db, User, Manga, Chapter, Genre
from auth import auth

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'  # Change this to a secure secret key
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///manga.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 64 * 1024 * 1024  # 64MB max file size
app.config['UPLOAD_FOLDER'] = os.path.join(app.static_folder, 'uploads')

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

db.init_app(app)

login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.init_app(app)

app.register_blueprint(auth, url_prefix='/auth')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def admin_required(f):
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

def timeago(date):
    now = datetime.now(timezone.utc)
    diff = now - date.replace(tzinfo=timezone.utc)
    
    seconds = diff.total_seconds()
    if seconds < 60:
        return "الآن"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f"{minutes} دقيقة"
    elif seconds < 86400:
        hours = int(seconds / 3600)
        return f"{hours} ساعة"
    elif seconds < 2592000:
        days = int(seconds / 86400)
        return f"{days} يوم"
    elif seconds < 31536000:
        months = int(seconds / 2592000)
        return f"{months} شهر"
    else:
        years = int(seconds / 31536000)
        return f"{years} سنة"

app.jinja_env.filters['timeago'] = timeago

@app.route('/')
def index():
    genre_id = request.args.get('genre_id', type=int)
    selected_genre = None
    
    # Base query for manga with eager loading of genres
    manga_query = Manga.query.options(db.joinedload(Manga.genres))
    
    if genre_id:
        selected_genre = Genre.query.get_or_404(genre_id)
        mangas = manga_query.join(Manga.genres).filter(Genre.id == genre_id).order_by(Manga.created_at.desc()).all()
    else:
        mangas = manga_query.order_by(Manga.created_at.desc()).all()
    
    # Get latest chapters with eager loading of manga
    latest_chapters = Chapter.query.options(
        db.joinedload(Chapter.manga)
    ).order_by(Chapter.created_at.desc()).limit(4).all()
    
    # Get all genres for filter
    all_genres = Genre.query.order_by(Genre.name).all()
    
    return render_template('index.html', 
                         mangas=mangas,
                         latest_chapters=latest_chapters,
                         all_genres=all_genres,
                         selected_genre=selected_genre)

@app.route('/upload_manga', methods=['GET', 'POST'])
@admin_required
def upload_manga():
    genres = Genre.query.order_by(Genre.name).all()
    
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        author = request.form.get('author')
        release_date = request.form.get('release_date')
        genre_ids = request.form.getlist('genres')
        cover = request.files.get('cover')

        if cover:
            filename = secure_filename(cover.filename)
            cover.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            
            manga = Manga(
                title=title,
                description=description,
                cover_image=filename,
                author=author,
                release_date=datetime.strptime(release_date, '%Y-%m-%d').date() if release_date else None,
                user_id=current_user.id
            )
            
            # Add selected genres
            selected_genres = Genre.query.filter(Genre.id.in_(genre_ids)).all()
            manga.genres.extend(selected_genres)
            
            db.session.add(manga)
            db.session.commit()
            flash('تم رفع المانجا بنجاح!', 'success')
            return redirect(url_for('index'))
    
    return render_template('upload_manga.html', genres=genres)

@app.route('/manga/<int:manga_id>')
def manga_detail(manga_id):
    manga = Manga.query.get_or_404(manga_id)
    return render_template('manga_detail.html', manga=manga)

@app.route('/manga/<int:manga_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_manga(manga_id):
    manga = Manga.query.get_or_404(manga_id)
    genres = Genre.query.order_by(Genre.name).all()
    
    if request.method == 'POST':
        manga.title = request.form.get('title')
        manga.description = request.form.get('description')
        manga.author = request.form.get('author')
        manga.release_date = datetime.strptime(request.form.get('release_date'), '%Y-%m-%d').date() if request.form.get('release_date') else None
        
        # Update cover if new one is uploaded
        cover = request.files.get('cover')
        if cover:
            filename = secure_filename(cover.filename)
            cover.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            manga.cover_image = filename
        
        # Update genres
        genre_ids = request.form.getlist('genres')
        selected_genres = Genre.query.filter(Genre.id.in_(genre_ids)).all()
        manga.genres = selected_genres
        
        db.session.commit()
        flash('تم تحديث المانجا بنجاح!', 'success')
        return redirect(url_for('manga_detail', manga_id=manga.id))
    
    return render_template('edit_manga.html', manga=manga, genres=genres)

@app.route('/manga/<int:manga_id>/upload_chapter', methods=['GET', 'POST'])
@admin_required
def upload_chapter(manga_id):
    manga = Manga.query.get_or_404(manga_id)
    
    if request.method == 'POST':
        chapter_number = request.form.get('chapter_number')
        chapter_title = request.form.get('chapter_title')
        pages = request.files.getlist('pages')
        
        if pages:
            page_paths = []
            for page in pages:
                filename = secure_filename(page.filename)
                page.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                page_paths.append(filename)
            
            chapter = Chapter(
                chapter_number=chapter_number,
                title=chapter_title,
                pages=','.join(page_paths),
                manga_id=manga_id,
                user_id=current_user.id
            )
            db.session.add(chapter)
            db.session.commit()
            flash('تم رفع الفصل بنجاح!', 'success')
            return redirect(url_for('manga_detail', manga_id=manga_id))
        else:
            flash('الرجاء تحديد صفحة واحدة على الأقل للرفع.', 'error')
    
    return render_template('upload_chapter.html', manga=manga)

@app.route('/chapter/<int:chapter_id>')
def read_chapter(chapter_id):
    chapter = Chapter.query.get_or_404(chapter_id)
    pages = chapter.pages.split(',')
    return render_template('read_chapter.html', chapter=chapter, pages=pages)

@app.route('/chapter/<int:chapter_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_chapter(chapter_id):
    chapter = Chapter.query.get_or_404(chapter_id)
    
    if request.method == 'POST':
        chapter.chapter_number = request.form.get('chapter_number')
        chapter.title = request.form.get('chapter_title')
        
        # Handle new pages if uploaded
        new_pages = request.files.getlist('new_pages')
        if new_pages and new_pages[0].filename:
            page_paths = []
            for page in new_pages:
                filename = secure_filename(page.filename)
                page.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                page_paths.append(filename)
            chapter.pages = ','.join(page_paths)
        
        db.session.commit()
        flash('تم تحديث الفصل بنجاح!', 'success')
        return redirect(url_for('read_chapter', chapter_id=chapter.id))
    
    return render_template('edit_chapter.html', chapter=chapter)

@app.route('/genres')
@admin_required
def manage_genres():
    genres = Genre.query.order_by(Genre.name).all()
    return render_template('manage_genres.html', genres=genres)

@app.route('/genres/add', methods=['POST'])
@admin_required
def add_genre():
    name = request.form.get('name')
    if name:
        genre = Genre(name=name)
        db.session.add(genre)
        db.session.commit()
        flash('تم إضافة التصنيف بنجاح!', 'success')
    return redirect(url_for('manage_genres'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
