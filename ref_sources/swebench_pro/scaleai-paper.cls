\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{scaleai-paper}[2023/04/01 Scale AI Conference Paper Class]
\LoadClass[danish,a4paper,10pt]{article}

% Required packages
\RequirePackage{geometry}
\RequirePackage{titlesec}
\RequirePackage{authblk}
\RequirePackage{graphicx}
\RequirePackage{fancyhdr}
\RequirePackage{microtype}
\usepackage[sfdefault]{inter}
\usepackage[table]{xcolor}
\usepackage[T1]{fontenc}
\RequirePackage{ragged2e}
% \usepackage{arev}
% \usepackage[T1]{fontenc}
% \usepackage[sfdefault]{FiraSans}
% \usepackage{newtxsf}



% Page geometry
\geometry{
    top=1.2in,
    bottom=1in,
    left=0.7in,
    right=0.7in
}


% % Remove lines in the title
% \newcommand{\@toptitlebar}{}
% \newcommand{\@bottomtitlebar}{}

% Font settings
% \renewcommand{\rmdefault}{ppl}
% \renewcommand{\sfdefault}{phv}

% Header and footer

\linespread{1}

\pagestyle{fancy}
\fancyhf{} % Clear all header and footer fields

\fancyhead[L]{%
  \includegraphics[height=0.5cm]{images/LogotypeGradientRGB.png} % Adjust the height and path as needed
}
\renewcommand{\headrulewidth}{0pt}
\cfoot{\thepage}

% Colors
\definecolor{scaleblue}{RGB}{0,123,255}

% Title formatting
\renewcommand{\maketitle}{%
\begin{flushleft}
{\linespread{1.0}\fontsize{25}{30}\selectfont\bfseries\@title\par}


\vspace{0.5cm}

\@author

\vspace{0.3cm}

% \@date
\end{flushleft}
}

\usepackage{titlesec}

% Section formatting
\titleformat{\section}
{\fontsize{14}{12}\bfseries}
{\thesection.}  % This adds the section number
{0.5em}  % This adds some space between the number and the title
{}

% % Section formatting
% \titleformat{\section}
% {\fontsize{14}{12}\bfseries}
% {}
% {0em}
% {}

% % Abstract environment
\renewenvironment{abstract}
{
\vspace{10pt}
\begin{flushleft}
\fontsize{15}{12}\textbf{Abstract}}
{\end{flushleft}
}

\renewenvironment{abstract}{
\vspace{10pt}
    \begin{flushleft}
{\fontsize{14}{12}\bfseries\abstractname\vspace{-.5em}\vspace{0pt}}
    \end{flushleft}
  \noindent
  \justifying % Ensure justification (requires ragged2e package)
}{
  \par\vspace{1.5em}
}



% Author formatting
% \renewcommand\Authfont{\linespread{1.4}\bfseries\fontsize{12}{11}\selectfont}
\renewcommand\Authfont{\linespread{1.5}\fontsize{12}{11}\bfseries\linespread{1.25}} % Adjust author font size


% Moderate spacing for sections
\titlespacing*{\section}{0pt}{2.6ex plus 1ex minus .2ex}{2.0ex plus .2ex}

% Moderate spacing for subsections
\titlespacing*{\subsection}{0pt}{2.6ex plus 1ex minus .2ex}{1.8ex plus .2ex}

% Moderate spacing for subsubsections
\titlespacing*{\subsubsection}{0pt}{2.4ex plus 1ex minus .2ex}{1.8ex plus .2ex}

% Moderate spacing for paragraphs
\titlespacing*{\paragraph}{0pt}{1.5ex plus 1ex minus .2ex}{1em}



% Adjust spacing
\setlength{\parskip}{4.5pt}
\setlength{\parindent}{0pt}
\setlength{\belowcaptionskip}{12pt}



\endinput