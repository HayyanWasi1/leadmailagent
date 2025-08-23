export function middleware(request) {
    const userName = request.cookies.get('user')?.value;

    if (userName) {
        if (request.nextUrl.pathname === '/login' || request.nextUrl.pathname === '/signup') {
            console.log(userName)
            return NextResponse.redirect(new URL('/', request.url))
        }
    } else if (!userName) {
        if (request.nextUrl.pathname === '/' || request.nextUrl.pathname === '/profile') {
            return NextResponse.redirect(new URL('/login', request.url))
        }
    }

}

export const config = {
    matcher: ['/login', '/signup', '/', '/profile']
}