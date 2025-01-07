// Preview uploaded images
document.addEventListener('DOMContentLoaded', function() {
    const coverInput = document.getElementById('cover');
    if (coverInput) {
        coverInput.addEventListener('change', function(e) {
            if (e.target.files && e.target.files[0]) {
                const reader = new FileReader();
                reader.onload = function(e) {
                    // You could add preview functionality here if needed
                };
                reader.readAsDataURL(e.target.files[0]);
            }
        });
    }

    // Handle multiple page uploads
    const pagesInput = document.getElementById('pages');
    if (pagesInput) {
        pagesInput.addEventListener('change', function(e) {
            const fileCount = e.target.files.length;
            const fileList = document.createElement('div');
            fileList.innerHTML = `Selected ${fileCount} page${fileCount !== 1 ? 's' : ''}`;
            this.parentNode.appendChild(fileList);
        });
    }
});
